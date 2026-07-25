from __future__ import annotations

import json as json_lib
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
from backend.services.llm_extraction import LLMExtractionService


class SemanticExtractorNode(BaseNode):
    type = "semantic-extractor"
    name = "Semantic Extractor"
    category = "extraction"
    icon = "\U0001f9e0"
    color = "#8b5cf6"
    description = "Extract structured fields from text using LLM — no regex, just descriptions"
    version = "1.0.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Raw text to extract fields from (from OCR or document parser)",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="extracted",
            type=PortType.JSON,
            label="Extracted Fields",
            description="Structured key-value pairs with confidence scores",
        ),
        Port(
            name="stats",
            type=PortType.JSON,
            label="Statistics",
            description="Match statistics (total, matched, unmatched, rate)",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID from /api/documents/upload. If empty, expects text from upstream input.",
        ),
        ConfigField(
            key="document_type",
            label="Document Type",
            type="select",
            required=False,
            default="generic",
            options=["generic", "invoice_fr", "invoice_ar", "custom"],
            description="Predefined document template with field descriptions",
        ),
        ConfigField(
            key="language",
            label="Language",
            type="select",
            required=False,
            default="fr",
            options=["fr", "en", "ar"],
            description="Document language for better extraction accuracy",
        ),
        ConfigField(
            key="fields",
            label="Custom Fields",
            type="json",
            required=False,
            default="[]",
            description="Inline JSON array of fields to extract. Used when document_type='custom'. Each field: {key, label, description, type?}. E.g. [{\"key\": \"date\", \"label\": \"Date\", \"description\": \"Document date\"}]",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            document_type = config.get("document_type", "generic")
            language = config.get("language", "fr")

            text = ctx.get_input("text", "")
            if not isinstance(text, str) or not text.strip():
                file_id = config.get("file_id", "")
                if not file_id:
                    result.fail("No text provided via input port or 'file_id' config")
                    return result
                text = await self._read_text_file(file_id)
                if not text:
                    result.fail(f"No readable text found for file '{file_id}'")
                    return result

            service = LLMExtractionService()

            if document_type == "custom":
                raw = config.get("fields", "[]")
                if isinstance(raw, str) and raw.strip():
                    fields = json_lib.loads(raw)
                elif isinstance(raw, list):
                    fields = raw
                else:
                    fields = []
            else:
                template = service.load_template(document_type)
                fields = template.get("fields", [])

            if not fields:
                result.fail("No fields defined. Provide a document_type or custom fields.")
                return result

            extraction_result = await service.extract(
                text=text,
                fields=fields,
                language=language,
            )

            result.succeed({
                "extracted": extraction_result["extracted"],
                "stats": extraction_result["stats"],
            })

        except Exception as e:
            result.fail(str(e))

        return result

    async def _read_text_file(self, file_id: str) -> str | None:
        import os

        upload_dir = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
        if not upload_dir.exists():
            return None
        for f in upload_dir.iterdir():
            if f.stem == file_id:
                return f.read_text(encoding="utf-8", errors="replace")
        return None
