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
from backend.services.ocr import OCRService
from backend.services.storage import StorageService


class OrientationDetectorNode(BaseNode):
    type = "orientation-detector"
    name = "Orientation Detector"
    category = "preprocessing"
    icon = "🔄"
    color = "#06b6d4"
    description = "Detect and correct page orientation"
    version = "1.0.0"

    inputs = [
        Port(
            name="image",
            type=PortType.IMAGE,
            label="Image/page",
            description="Image or page whose orientation needs to be corrected",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="image",
            type=PortType.IMAGE,
            label="Reoriented page",
            description="Image/page with corrected orientation",
        ),
        Port(
            name="metadata",
            type=PortType.JSON,
            label="Metadata",
            description="Information on detected orientation and applied correction",
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

            file_data: dict[str, Any] | None = (
                ctx.get_input("image") or ctx.get_input("input") or ctx.get_input("document")
            )
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
                    f"File extension '{ext}' not allowed. Orientation Detector only supports images. Allowed: {allowed_exts}"
                )
                return result

            if size_bytes > max_bytes:
                result.fail(
                    f"File size {size_bytes} bytes exceeds maximum of {max_bytes} bytes"
                )
                return result

            # Detect orientation using OCRService
            ocr_service = OCRService()
            detection = await ocr_service.detect_orientation(file_path)
            detected_angle = detection.get("angle", 0)
            confidence = detection.get("confidence", 1.0)

            from PIL import Image

            with Image.open(file_path) as image:
                # Rotate image if detected angle is non-zero
                if detected_angle != 0:
                    # In PIL rotate, positive values rotate counter-clockwise.
                    # Tesseract's 'Rotate:' value is already in degrees counter-clockwise.
                    corrected_image = image.rotate(detected_angle, expand=True)
                else:
                    corrected_image = image.copy()

                out_path = Path(f"data/storage/{uuid.uuid4().hex}{ext}")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                corrected_image.save(out_path)

                metadata = {
                    "filename": original_name,
                    "source_path": str(file_path),
                    "output_path": str(out_path),
                    "size_bytes": out_path.stat().st_size,
                    "detected_angle": detected_angle,
                    "confidence": confidence,
                    "rotation_applied": detected_angle != 0,
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
