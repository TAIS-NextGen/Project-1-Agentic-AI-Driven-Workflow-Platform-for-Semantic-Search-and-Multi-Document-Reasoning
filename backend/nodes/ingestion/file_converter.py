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
from backend.services.conversion import FileConversionService


class FileConverterNode(BaseNode):
    type = "file-converter"
    name = "File Converter"
    category = "ingestion"
    icon = "🔄"
    color = "#3b82f6"
    description = "Convert DOCX/PPTX/images to PDF, or extract plain text from DOCX"
    version = "1.0.0"

    inputs = [
        Port(
            name="document",
            type=PortType.DOCUMENT,
            label="Document",
            description="Source file to convert (DOCX, PPTX, image, etc.)",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="converted_path",
            type=PortType.DOCUMENT,
            label="Converted File",
            description="Path to the converted PDF (or original path if already PDF)",
        ),
        Port(
            name="text",
            type=PortType.TEXT,
            label="Extracted Text",
            description="Plain text, if output_mode is 'text' and format supports it",
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
            key="output_mode",
            label="Output Mode",
            type="text",
            required=False,
            default="pdf",
            description="'pdf' to convert to PDF, or 'text' to extract plain text (DOCX only)",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            output_mode = config.get("output_mode", "pdf")

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

            service = FileConversionService()

            if output_mode == "text":
                extraction = await service.extract_text(file_path)
                result.succeed({
                    "converted_path": str(file_path),
                    "text": extraction["text"],
                })
            else:
                output_dir = Path(os.getenv("UPLOAD_DIR", "data/uploads")) / "converted"
                conversion = await service.convert_to_pdf(file_path, output_dir)
                result.succeed({
                    "converted_path": conversion["output_path"],
                    "text": "",
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