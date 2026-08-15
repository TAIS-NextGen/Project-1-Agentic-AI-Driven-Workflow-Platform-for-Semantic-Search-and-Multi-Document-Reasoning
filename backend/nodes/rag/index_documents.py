from __future__ import annotations

from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)


class IndexDocumentsNode(BaseNode):
    type = "index-documents"
    name = "Index Documents"
    category = "rag"
    icon = "\U0001f4da"
    color = "#a855f7"
    description = "Extract text, chunk and embed a batch of documents into the persistent retrieval index"
    version = "1.0.0"

    inputs = [
        Port(
            name="file_ids",
            type=PortType.JSON,
            label="File IDs",
            description="Array of library file IDs to index (from Document Batch Upload)",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="status",
            type=PortType.JSON,
            label="Index Status",
            description="Number of indexed documents, chunks, and extraction methods used",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_ids",
            label="File IDs (comma-separated)",
            type="text",
            required=False,
            default="",
            description="Fallback file IDs to index if none are provided via the input port.",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()

            file_ids: list[str] = []

            input_ids = ctx.get_input("file_ids")
            if isinstance(input_ids, (list, tuple)):
                file_ids = [str(fid) for fid in input_ids]
            elif isinstance(input_ids, str):
                file_ids = [fid.strip() for fid in input_ids.split(",") if fid.strip()]

            if not file_ids:
                raw = str(config.get("file_ids", "")).strip()
                file_ids = [fid.strip() for fid in raw.split(",") if fid.strip()]

            if not file_ids:
                result.fail("No file IDs provided via input port or 'file_ids' config")
                return result

            from backend.services.qa_index import QAIndexService

            svc = QAIndexService()
            status = await svc.index_documents(file_ids)

            result.succeed({"status": status})

        except Exception as e:
            result.fail(f"Index Documents failed: {e}")

        return result
