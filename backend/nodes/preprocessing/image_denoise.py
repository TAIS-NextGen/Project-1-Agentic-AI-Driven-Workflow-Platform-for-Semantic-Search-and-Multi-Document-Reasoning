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
from backend.services.storage import StorageService


class ImageDenoiseNode(BaseNode):
    type = "image-denoise"
    name = "Image Denoise"
    category = "preprocessing"
    icon = "🧼"
    color = "#10b981"
    description = "Reduce noise in an image and emit a cleaned image output"
    version = "1.0.0"

    inputs = [
        Port(
            name="image",
            type=PortType.IMAGE,
            label="Image",
            description="Image input to denoise",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="image",
            type=PortType.IMAGE,
            label="Denoised Image",
            description="Processed image with reduced noise",
        ),
        Port(
            name="metadata",
            type=PortType.JSON,
            label="Metadata",
            description="Processing metadata, filename, and method details",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID from upload storage. If empty, expects image from upstream input.",
        ),
        ConfigField(
            key="allowed_extensions",
            label="Allowed Extensions",
            type="tags",
            required=False,
            default=[".png", ".jpg", ".jpeg", ".tiff", ".bmp"],
            description="Accepted image file extensions",
        ),
        ConfigField(
            key="max_file_size_mb",
            label="Max File Size (MB)",
            type="number",
            required=False,
            default=50,
            description="Maximum allowed file size in megabytes",
        ),
        ConfigField(
            key="method",
            label="Denoise Method",
            type="text",
            required=False,
            default="pil-median",
            description="Processing strategy to apply: pil-median",
        ),
    ]

    @staticmethod
    def _get_upload_dir() -> Path:
        return Path(os.getenv("UPLOAD_DIR", "data/uploads"))

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            allowed_exts: list[str] = config.get("allowed_extensions", [])
            max_bytes = int(config.get("max_file_size_mb", 50)) * 1024 * 1024
            method = config.get("method", "pil-median")

            file_data: dict[str, Any] | None = ctx.get_input("image")
            if not file_data:
                file_id = config.get("file_id", "")
                if not file_id:
                    result.fail("No image provided via input port or 'file_id' config")
                    return result
                file_data = await self._resolve_by_file_id(file_id)
                if not file_data:
                    result.fail(f"Image with ID '{file_id}' not found in upload directory")
                    return result

            path_val = file_data.get("path") or file_data.get("file_path")
            if not path_val:
                result.fail("No file path found in input dictionary ('path' or 'file_path')")
                return result
            file_path = Path(path_val)
            if not file_path.exists():
                result.fail(f"File not found at path: {file_path}")
                return result

            original_name = file_data.get("filename", file_path.name)
            size_bytes = file_data.get("size_bytes", file_path.stat().st_size)
            ext = file_path.suffix.lower()
            if ext not in allowed_exts:
                result.fail(
                    f"File extension '{ext}' not allowed. Denoise only supports images. Allowed: {allowed_exts}"
                )
                return result

            if size_bytes > max_bytes:
                result.fail(
                    f"File size {size_bytes} bytes exceeds maximum of {max_bytes} bytes"
                )
                return result

            from PIL import Image, ImageFilter

            with Image.open(file_path) as image:
                image = image.convert("RGB")
                if method == "pil-median":
                    filtered = image.filter(ImageFilter.MedianFilter(size=3))
                else:
                    filtered = image.filter(ImageFilter.GaussianBlur(radius=1))

                storage = StorageService()
                out_path = Path(f"data/storage/{uuid.uuid4().hex}{ext}")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                filtered.save(out_path)

                metadata = {
                    "filename": original_name,
                    "source_path": str(file_path),
                    "output_path": str(out_path),
                    "size_bytes": out_path.stat().st_size,
                    "denoise_method": method,
                    "input_format": ext,
                }

                result.succeed({
                    "image": {
                        "filename": original_name,
                        "path": str(out_path),
                        "file_path": str(out_path),
                        "size_bytes": out_path.stat().st_size,
                        "mime_type": "image/png" if ext.lower() == ".png" else "image/jpeg",
                    },
                    "metadata": metadata,
                })
        except Exception as e:
            result.fail(str(e))

        return result

    async def _resolve_by_file_id(self, file_id: str) -> dict[str, Any] | None:
        upload_dir = self._get_upload_dir()
        if not upload_dir.exists():
            return None
        for f in upload_dir.iterdir():
            if f.stem == file_id:
                return {
                    "file_id": file_id,
                    "filename": f.name,
                    "path": str(f),
                    "size_bytes": f.stat().st_size,
                }
        return None
