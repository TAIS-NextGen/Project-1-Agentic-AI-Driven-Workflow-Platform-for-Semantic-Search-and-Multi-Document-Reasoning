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
from backend.services.extraction import RegexExtractionService


class RegexExtractorNode(BaseNode):
    type = "regex-extractor"
    name = "Regex Extractor"
    category = "extraction"
    icon = "🔍"
    color = "#f59e0b"
    description = "Extract structured fields from text using regex patterns and document templates"
    version = "1.0.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Raw text to extract fields from (from OCR or parser)",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="extracted",
            type=PortType.JSON,
            label="Extracted Fields",
            description="Structured key-value pairs grouped by category with confidence scores",
        ),
        Port(
            name="missing",
            type=PortType.JSON,
            label="Missing Fields",
            description="Required fields that were not found in the text",
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
            description="File ID containing text to parse. If empty, expects text from upstream input.",
        ),
        ConfigField(
            key="template",
            label="Template",
            type="text",
            required=False,
            default="generic",
            description="Document template name: generic, invoice_ar, invoice_fr, or custom",
        ),
        ConfigField(
            key="language",
            label="Language",
            type="text",
            required=False,
            default="fr",
            description="Document language (ar, fr, en)",
        ),
        ConfigField(
            key="custom_patterns",
            label="Custom Patterns",
            type="json",
            required=False,
            default="[]",
            description="Custom JSON array of pattern definitions (used if template='custom')",
        ),
        ConfigField(
            key="text",
            label="Text",
            type="text",
            required=False,
            default="",
            description="Text to extract patterns from. Leave empty if provided via upstream connection.",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            template = config.get("template", "generic")
            language = config.get("language", "fr")

            text = ctx.get_input("text", "") or str(config.get("text", ""))
            if not isinstance(text, str) or not text.strip():
                file_id = config.get("file_id", "")
                if not file_id:
                    result.fail("No text provided via input port or 'file_id' config")
                    return result
                text = await self._read_text_file(file_id)
                if not text:
                    result.fail(f"No readable text found for file '{file_id}'")
                    return result

            service = RegexExtractionService(language=language)

            if template == "custom":
                raw = config.get("custom_patterns", "[]")
                if isinstance(raw, str):
                    patterns = json_lib.loads(raw)
                else:
                    patterns = raw
            else:
                template_data = service.load_template(template)
                patterns = template_data.get("patterns", [])

            extraction_result = service.extract(text, patterns)

            result.succeed({
                "extracted": extraction_result["extracted"],
                "missing": extraction_result["missing"],
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
