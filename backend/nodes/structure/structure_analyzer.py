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
from backend.services.structure import StructureAnalyzerService


class DocumentStructureAnalyzerNode(BaseNode):
    type = "document-structure-analyzer"
    name = "Document Structure Analyzer"
    category = "structure"
    icon = "🏗️"
    color = "#6366f1"
    description = "Detect document layout: titles, paragraphs, tables, figures, headers, footers"
    version = "1.0.0"

    inputs = [
        Port(
            name="document",
            type=PortType.DOCUMENT,
            label="Document",
            description="Document to analyze (from DocumentUpload or upstream node)",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="structure",
            type=PortType.JSON,
            label="Structure Map",
            description="Full document layout: pages, blocks, types, positions, text",
        ),
        Port(
            name="summary",
            type=PortType.JSON,
            label="Summary",
            description="Element type counts across all pages",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID from /api/documents/upload. If empty, expects document from upstream input.",
        ),
        ConfigField(
            key="allowed_extensions",
            label="Allowed Extensions",
            type="tags",
            required=False,
            default=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"],
            description="Accepted document file extensions",
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
            key="strategy",
            label="Partition Strategy",
            type="text",
            required=False,
            default="auto",
            description="Unstructured partition strategy: 'auto', 'fast' (no OCR), or 'hi_res' (requires Tesseract)",
        ),
        ConfigField(
            key="language",
            label="OCR Languages",
            type="text",
            required=False,
            default="ara+eng+fra",
            description="Tesseract language codes for OCR, joined by '+'. e.g. 'ara+eng+fra', 'deu', 'chi_sim+chi_tra'",
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
            strategy = config.get("strategy", "auto")
            language = config.get("language", "ara+eng+fra")

            file_data: dict[str, Any] | None = ctx.get_input("document")

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
                    f"File extension '{ext}' not allowed. Allowed: {allowed_exts}"
                )
                return result

            if size_bytes > max_bytes:
                result.fail(
                    f"File size {size_bytes} bytes exceeds maximum of {max_bytes} bytes"
                )
                return result

            analyzer = StructureAnalyzerService()
            analysis = await analyzer.analyze(str(file_path), strategy=strategy, languages=language)

            result.succeed({
                "structure": analysis["pages"],
                "summary": {
                    **analysis["summary"],
                    "filename": original_name,
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
