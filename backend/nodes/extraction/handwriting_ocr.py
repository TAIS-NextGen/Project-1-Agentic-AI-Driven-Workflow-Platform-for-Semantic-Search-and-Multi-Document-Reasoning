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


class HandwritingOCRNode(BaseNode):
    type = "handwriting-ocr"
    name = "Handwriting OCR"
    category = "extraction"
    icon = "✍️"
    color = "#8b5cf6"
    description = "Extract handwritten text from images using OCR (supports Arabic, French, English)"
    version = "1.0.0"

    inputs = [
        Port(
            name="image",
            type=PortType.IMAGE,
            label="Image",
            description="Handwritten document image from upstream node",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Extracted Text",
            description="Full extracted handwritten text",
        ),
        Port(
            name="confidence",
            type=PortType.JSON,
            label="Confidence",
            description="Average OCR confidence score (0-1)",
        ),
        Port(
            name="details",
            type=PortType.JSON,
            label="Details",
            description="Per-line text with individual confidence scores",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID from /api/documents/upload. If empty, expects image from upstream input.",
        ),
        ConfigField(
            key="language",
            label="Language",
            type="text",
            required=False,
            default="ar",
            description="OCR language code (ar, fr, en, or comma-separated like 'ar,en')",
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
            language = config.get("language", "ar")

            file_data: dict[str, Any] | None = ctx.get_input("image")

            if not file_data:
                file_id = config.get("file_id", "")
                if not file_id:
                    result.fail("No file provided via input port or 'file_id' config")
                    return result
                file_data = await self._resolve_by_file_id(file_id)
                if not file_data:
                    result.fail(f"File with ID '{file_id}' not found in upload directory")
                    return result

            file_path = Path(file_data["path"])
            if not file_path.exists():
                result.fail(f"File not found at path: {file_path}")
                return result

            original_name = file_data.get("filename", file_path.name)
            size_bytes = file_data.get("size_bytes", file_path.stat().st_size)

            ext = file_path.suffix.lower()
            if ext not in allowed_exts:
                result.fail(
                    f"File extension '{ext}' not allowed. HandwritingOCR only supports images. "
                    f"Allowed: {allowed_exts}"
                )
                return result

            if size_bytes > max_bytes:
                result.fail(
                    f"File size {size_bytes} bytes exceeds maximum of {max_bytes} bytes"
                )
                return result

            ocr = OCRService(lang=language)
            ocr_result = await ocr.extract_text(str(file_path))

            result.succeed({
                "text": ocr_result["text"],
                "confidence": ocr_result["confidence"],
                "details": {
                    "lines": ocr_result["lines"],
                    "total_lines": ocr_result["total_lines"],
                    "filename": original_name,
                    "language": language,
                },
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
