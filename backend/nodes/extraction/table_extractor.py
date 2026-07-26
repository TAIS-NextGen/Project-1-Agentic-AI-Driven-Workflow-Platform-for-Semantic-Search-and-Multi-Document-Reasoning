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
from backend.services.table_extraction import TableExtractionService


class TableExtractorNode(BaseNode):
    type = "table-extractor"
    name = "Table Extractor"
    category = "extraction"
    icon = "📊"
    color = "#ec4899"
    description = "Detect tables in a page/region and extract row/column structure"
    version = "1.0.0"

    inputs = [
        Port(
            name="document",
            type=PortType.DOCUMENT,
            label="Page Image",
            description="Page or region image to search for tables",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="tables",
            type=PortType.JSON,
            label="Tables",
            description="List of detected tables with bounding boxes, row/column counts, and cells",
        ),
        Port(
            name="table_count",
            type=PortType.JSON,
            label="Table Count",
            description="Number of tables detected",
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
            key="confidence_threshold",
            label="Confidence Threshold",
            type="number",
            required=False,
            default=0.7,
            description="Minimum detection confidence (0-1) for tables and structure elements",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            threshold = float(config.get("confidence_threshold", 0.7))

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

            service = TableExtractionService()
            extraction = await service.extract(file_path, confidence_threshold=threshold)

            result.succeed({
                "tables": extraction["tables"],
                "table_count": extraction["table_count"],
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