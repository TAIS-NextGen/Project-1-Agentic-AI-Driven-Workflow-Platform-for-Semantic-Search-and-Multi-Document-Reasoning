from __future__ import annotations

import json
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


class RouterNode(BaseNode):
    type = "router"
    name = "Router (Rule-Based)"
    category = "orchestration"
    icon = "\U0001f9ed"
    color = "#a855f7"
    description = "Deterministically select the downstream extraction branch from the document extension"
    version = "1.0.0"

    inputs = [
        Port(
            name="document",
            type=PortType.DOCUMENT,
            label="Document",
            description="Document reference with filename (from Document Upload)",
            required=False,
        ),
        Port(
            name="filename",
            type=PortType.TEXT,
            label="Filename",
            description="Original filename (fallback if no document is connected)",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="route",
            type=PortType.TEXT,
            label="Route",
            description="Selected branch name (e.g. 'ocr' or 'parser')",
        ),
        Port(
            name="confidence",
            type=PortType.JSON,
            label="Confidence",
            description="Deterministic rule confidence (always 1.0)",
        ),
    ]

    config_fields = [
        ConfigField(
            key="rules",
            label="Routing Rules",
            type="json",
            required=False,
            default=[
                {"route": "parser", "extensions": [".docx", ".pdf"]},
                {"route": "ocr", "extensions": [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]},
            ],
            description="Ordered list of {route, extensions} rules. First matching extension wins.",
        ),
        ConfigField(
            key="default_route",
            label="Default Route",
            type="text",
            required=False,
            default="ocr",
            description="Route used when no rule matches the document extension",
        ),
    ]

    def _resolve_filename(self, ctx: ExecutionContext, config: dict[str, Any]) -> str:
        filename = str(ctx.get_input("filename", "") or "").strip()
        document = ctx.get_input("document")
        if isinstance(document, dict):
            filename = filename or str(
                document.get("filename", "")
                or document.get("file_name", "")
                or document.get("path", "")
                or document.get("file_path", "")
            ).strip()
        elif isinstance(document, str):
            filename = filename or document.strip()
        return filename

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            filename = self._resolve_filename(ctx, config)

            if not filename:
                result.fail("No document or filename provided to the Router")
                return result

            extension = Path(filename).suffix.lower()

            rules = config.get("rules", [])
            if isinstance(rules, str) and rules.strip():
                try:
                    rules = json.loads(rules)
                except (json.JSONDecodeError, TypeError):
                    rules = []
            if not isinstance(rules, list):
                rules = []

            route = str(config.get("default_route", "ocr"))
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                extensions = rule.get("extensions", [])
                if isinstance(extensions, str):
                    extensions = [extensions]
                extensions = {str(e).lower() for e in extensions if isinstance(e, str)}
                if extension in extensions:
                    route = str(rule.get("route", route))
                    break

            result.succeed({
                "route": route,
                "confidence": {"confidence": 1.0},
            })

        except Exception as e:
            result.fail(f"Router failed: {e}")

        return result
