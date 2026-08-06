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
from backend.services.translation import TranslationService


class TranslatorNode(BaseNode):
    type = "translator"
    name = "Translator"
    category = "analysis"
    icon = "🌐"
    color = "#f59e0b"
    description = "Translate text between languages using offline Argos Translate models"
    version = "1.0.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Text to translate",
            required=True,
        ),
    ]

    outputs = [
        Port(
            name="translated_text",
            type=PortType.TEXT,
            label="Translated Text",
            description="Translated output text",
        ),
    ]

    config_fields = [
        ConfigField(
            key="from_language",
            label="From Language",
            type="text",
            required=False,
            default="fr",
            description="Source language code (e.g. fr, en, ar)",
        ),
        ConfigField(
            key="to_language",
            label="To Language",
            type="text",
            required=False,
            default="en",
            description="Target language code (e.g. fr, en, ar)",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            from_lang = config.get("from_language", "fr")
            to_lang = config.get("to_language", "en")

            text = ctx.get_input("text", "")
            if not isinstance(text, str) or not text.strip():
                result.fail("No text provided via input port")
                return result

            service = TranslationService()
            translation = service.translate(text, from_lang, to_lang)

            result.succeed({"translated_text": translation["translated_text"]})

        except Exception as e:
            result.fail(str(e))

        return result