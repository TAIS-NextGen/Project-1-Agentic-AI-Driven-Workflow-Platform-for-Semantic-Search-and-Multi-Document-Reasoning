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
from backend.services.summarizer import SummarizerService


class SummarizerNode(BaseNode):
    type = "summarizer"
    name = "Summarizer Agent"
    category = "agents"
    icon = "📝"
    color = "#ec4899"
    description = "Generate a summary of the provided text in various styles"
    version = "1.0.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Document text or chunks to summarize",
            required=True,
        ),
    ]

    outputs = [
        Port(
            name="summary",
            type=PortType.TEXT,
            label="Summary",
            description="The generated summary",
        ),
    ]

    config_fields = [
        ConfigField(
            key="style",
            label="Summary Style",
            type="select",
            required=True,
            default="short",
            description="Format of the summary (short, long, bullet_points, executive)",
            options=["short", "long", "bullet_points", "executive"],
        ),
        ConfigField(
            key="model",
            label="LLM Model",
            type="text",
            required=False,
            default="",
            description="Optional model override (e.g. gpt-4o). Leaves empty for default.",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            style = config.get("style", "short")
            model = config.get("model", "")

            text = ctx.get_input("text", "")
            if not isinstance(text, str) or not text.strip():
                result.fail("No valid text provided for summarization")
                return result

            service = SummarizerService(model=model)
            summary = await service.summarize(text=text, style=style)

            result.succeed({"summary": summary})

        except Exception as e:
            result.fail(f"Summarizer node execution failed: {e}")

        return result
