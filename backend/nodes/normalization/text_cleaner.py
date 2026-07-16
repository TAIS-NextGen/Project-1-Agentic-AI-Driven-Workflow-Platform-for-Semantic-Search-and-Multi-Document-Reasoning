from __future__ import annotations

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
from backend.services.normalization import TextCleanerService


class TextCleanerNode(BaseNode):
    type = "text-cleaner"
    name = "Text Cleaner"
    category = "normalization"
    icon = "🧹"
    color = "#22c55e"
    description = "Clean and normalize raw text: whitespace, hyphenation, casing, dates"
    version = "1.0.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Raw text to clean (from OCR or parser)",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="cleaned_text",
            type=PortType.TEXT,
            label="Cleaned Text",
            description="Normalized, cleaned text",
        ),
        Port(
            name="stats",
            type=PortType.JSON,
            label="Statistics",
            description="Cleaning statistics (length change, dates normalized)",
        ),
        Port(
            name="dates",
            type=PortType.JSON,
            label="Normalized Dates",
            description="List of original/normalized date pairs found in the text",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID containing text to clean. If empty, expects text from upstream input.",
        ),
        ConfigField(
            key="fix_hyphenation",
            label="Fix Hyphenation",
            type="boolean",
            required=False,
            default=True,
            description="Join words broken across lines by a hyphen (e.g. 'docu-\\nment')",
        ),
        ConfigField(
            key="collapse_whitespace",
            label="Collapse Whitespace",
            type="boolean",
            required=False,
            default=True,
            description="Collapse repeated spaces/newlines and trim lines",
        ),
        ConfigField(
            key="strip_special_chars",
            label="Strip Special Characters",
            type="boolean",
            required=False,
            default=False,
            description="Remove characters outside common punctuation and letters/digits",
        ),
        ConfigField(
            key="normalize_casing",
            label="Normalize Casing",
            type="text",
            required=False,
            default="",
            description="One of: lower, upper, title, or empty for no change",
        ),
        ConfigField(
            key="normalize_dates",
            label="Normalize Dates",
            type="boolean",
            required=False,
            default=False,
            description="Detect and reformat date-like substrings",
        ),
        ConfigField(
            key="date_output_format",
            label="Date Output Format",
            type="text",
            required=False,
            default="%Y-%m-%d",
            description="strftime format used when normalize_dates is enabled",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()

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

            casing = config.get("normalize_casing", "") or None

            service = TextCleanerService()
            cleaned = service.clean(
                text,
                fix_hyphenation=bool(config.get("fix_hyphenation", True)),
                collapse_whitespace=bool(config.get("collapse_whitespace", True)),
                strip_special_chars=bool(config.get("strip_special_chars", False)),
                normalize_casing=casing,
                normalize_dates=bool(config.get("normalize_dates", False)),
                date_output_format=config.get("date_output_format", "%Y-%m-%d"),
            )

            result.succeed({
                "cleaned_text": cleaned["cleaned_text"],
                "stats": cleaned["stats"],
                "dates": cleaned["dates"],
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