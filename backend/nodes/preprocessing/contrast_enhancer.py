from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)


class ContrastEnhancerNode(BaseNode):
    type = "contrast-enhancer"
    name = "Contrast Enhancer"
    category = "preprocessing"
    icon = "☀️"
    color = "#f59e0b"
    description = "Improve image readability by adjusting contrast, brightness, sharpness, and tonal range"
    version = "1.0.0"

    inputs = [
        Port(
            name="image",
            type=PortType.IMAGE,
            label="Image",
            description="Image to enhance",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="image",
            type=PortType.IMAGE,
            label="Enhanced Image",
            description="Image with improved contrast and brightness",
        ),
        Port(
            name="metadata",
            type=PortType.JSON,
            label="Enhancement Metadata",
            description="Applied settings and luminance measurements",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="Uploaded image ID. Leave empty when an upstream image is connected.",
        ),
        ConfigField(
            key="contrast",
            label="Contrast",
            type="slider",
            required=False,
            default=1.35,
            description="Contrast multiplier. 1.0 keeps the original contrast.",
        ),
        ConfigField(
            key="brightness",
            label="Brightness",
            type="slider",
            required=False,
            default=1.08,
            description="Brightness multiplier. 1.0 keeps the original brightness.",
        ),
        ConfigField(
            key="sharpness",
            label="Sharpness",
            type="slider",
            required=False,
            default=1.1,
            description="Sharpness multiplier. 1.0 keeps the original sharpness.",
        ),
        ConfigField(
            key="auto_contrast",
            label="Automatic Contrast",
            type="boolean",
            required=False,
            default=True,
            description="Stretch the tonal range before applying manual adjustments.",
        ),
        ConfigField(
            key="cutoff",
            label="Auto-contrast Cutoff (%)",
            type="number",
            required=False,
            default=1,
            description="Percentage of extreme pixels ignored by auto contrast.",
        ),
        ConfigField(
            key="max_file_size_mb",
            label="Max File Size (MB)",
            type="number",
            required=False,
            default=50,
        ),
    ]

    @staticmethod
    def _get_upload_dir() -> Path:
        return Path(os.getenv("UPLOAD_DIR") or os.getenv("SYMPACT_UPLOAD_DIR") or "data/uploads")

    @staticmethod
    def _get_storage_dir() -> Path:
        return Path(os.getenv("STORAGE_DIR") or os.getenv("SYMPACT_STORAGE_DIR") or "data/storage")

    @staticmethod
    def _resolve_file_data(ctx: ExecutionContext, config: dict[str, Any]) -> dict[str, Any] | None:
        file_data = ctx.get_input("image")
        if file_data:
            return file_data

        file_id = str(config.get("file_id", "")).strip()
        if not file_id:
            return None

        upload_dir = ContrastEnhancerNode._get_upload_dir()
        if not upload_dir.exists():
            return None

        for file_path in upload_dir.iterdir():
            if file_path.stem == file_id:
                return {
                    "file_id": file_id,
                    "filename": str(config.get("filename") or file_path.name),
                    "path": str(file_path),
                    "size_bytes": file_path.stat().st_size,
                }
        return None

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            from PIL import Image, ImageEnhance, ImageOps, ImageStat

            config = self.get_resolved_config()
            file_data = self._resolve_file_data(ctx, config)
            if not file_data:
                result.fail("No image provided via input port or 'file_id' config")
                return result

            path_value = file_data.get("path") or file_data.get("file_path")
            if not path_value:
                result.fail("No file path found in image input")
                return result

            file_path = Path(path_value)
            if not file_path.exists():
                result.fail(f"File not found at path: {file_path}")
                return result

            allowed_extensions = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
            extension = file_path.suffix.lower()
            if extension not in allowed_extensions:
                result.fail(
                    f"File extension '{extension}' is not supported. Allowed: {sorted(allowed_extensions)}"
                )
                return result

            max_bytes = int(config.get("max_file_size_mb", 50)) * 1024 * 1024
            size_bytes = int(file_data.get("size_bytes", file_path.stat().st_size))
            if size_bytes > max_bytes:
                result.fail(f"File size {size_bytes} bytes exceeds maximum of {max_bytes} bytes")
                return result

            contrast = max(0.1, float(config.get("contrast", 1.35)))
            brightness = max(0.1, float(config.get("brightness", 1.08)))
            sharpness = max(0.0, float(config.get("sharpness", 1.1)))
            auto_contrast = bool(config.get("auto_contrast", True))
            cutoff = min(max(float(config.get("cutoff", 1)), 0.0), 20.0)

            with Image.open(file_path) as source:
                original_mode = source.mode
                alpha = source.getchannel("A") if "A" in source.getbands() else None
                working = source.convert("RGB")
                before_luminance = round(float(ImageStat.Stat(working.convert("L")).mean[0]), 2)

                if auto_contrast:
                    working = ImageOps.autocontrast(working, cutoff=cutoff)
                working = ImageEnhance.Contrast(working).enhance(contrast)
                working = ImageEnhance.Brightness(working).enhance(brightness)
                working = ImageEnhance.Sharpness(working).enhance(sharpness)

                after_luminance = round(float(ImageStat.Stat(working.convert("L")).mean[0]), 2)

                if alpha is not None:
                    working = working.convert("RGBA")
                    working.putalpha(alpha)

                output_path = self._get_storage_dir() / f"{uuid.uuid4().hex}.png"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                working.save(output_path, format="PNG", optimize=True)

            original_name = str(file_data.get("filename") or file_path.name)
            output_name = f"{Path(original_name).stem}-enhanced.png"
            output_size = output_path.stat().st_size

            result.succeed(
                {
                    "image": {
                        "filename": output_name,
                        "path": str(output_path),
                        "file_path": str(output_path),
                        "size_bytes": output_size,
                        "mime_type": "image/png",
                    },
                    "metadata": {
                        "source_filename": original_name,
                        "source_path": str(file_path),
                        "output_path": str(output_path),
                        "original_mode": original_mode,
                        "contrast": contrast,
                        "brightness": brightness,
                        "sharpness": sharpness,
                        "auto_contrast": auto_contrast,
                        "cutoff": cutoff,
                        "luminance_before": before_luminance,
                        "luminance_after": after_luminance,
                    },
                }
            )
        except ImportError as exc:
            result.fail(f"Contrast enhancement dependency missing: {exc}. Install Pillow.")
        except Exception as exc:
            result.fail(str(exc))

        return result
