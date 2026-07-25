from __future__ import annotations

import os
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
from backend.services.ocr import TesseractOCRService


class OCRNode(BaseNode):
    type = "ocr-node"
    name = "OCR Node"
    category = "extraction"
    icon = "📄"
    color = "#f59e0b"
    description = "Convert printed/scanned images or PDFs to text using Tesseract"
    version = "1.0.0"

    inputs = [
        Port(
            name="document",
            type=PortType.DOCUMENT,
            label="Document",
            description="Scanned image or PDF to run OCR on",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Extracted Text",
            description="Full text extracted from the document",
        ),
        Port(
            name="lines",
            type=PortType.JSON,
            label="Lines",
            description="Per-line text with confidence scores",
        ),
        Port(
            name="stats",
            type=PortType.JSON,
            label="Statistics",
            description="Average confidence, total lines/pages",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID from upload. If empty, expects document from upstream input.",
        ),
        ConfigField(
            key="language",
            label="Language",
            type="text",
            required=False,
            default="eng",
            description="Tesseract language code (e.g. eng, fra, ara). Combine with '+' for multiple.",
        ),
        ConfigField(
            key="dpi",
            label="PDF DPI",
            type="number",
            required=False,
            default=300,
            description="Resolution used when rasterizing PDF pages before OCR",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            language = config.get("language", "eng")
            dpi = int(config.get("dpi", 300))

            file_data: dict[str, Any] | None = ctx.get_input("document")

            if not file_data:
                file_id = config.get("file_id", "")
                if not file_id:
                    result.fail("No document provided via input port or 'file_id' config")
                    return result
                file_data = await self._resolve_by_file_id(file_id)
                if not file_data:
                    result.fail(f"File with ID '{file_id}' not found in upload directory")
                    return result

            file_path = Path(file_data["path"])
            if not file_path.exists():
                result.fail(f"File not found at path: {file_path}")
                return result

            service = TesseractOCRService(lang=language)

            if file_path.suffix.lower() == ".pdf":
                extraction = await service.extract_text_from_pdf(
                    file_path, lang=language, dpi=dpi
                )
            else:
                extraction = await service.extract_text(file_path, lang=language)

            result.succeed({
                "text": extraction["text"],
                "lines": extraction["lines"],
                "stats": {
                    "confidence": extraction["confidence"],
                    "total_lines": extraction["total_lines"],
                    "total_pages": extraction.get("total_pages", 1),
                },
            })

        except Exception as e:
            result.fail(str(e))

        return result

    async def _resolve_by_file_id(self, file_id: str) -> dict[str, Any] | None:
        upload_dir = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
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