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
from backend.services.table_agent import TableAgentService


class TableAgentNode(BaseNode):
    type = "table-agent"
    name = "Table Agent"
    category = "agents"
    icon = "📋"
    color = "#a855f7"
    description = "Reason over structured tables to answer questions (beyond raw extraction)"
    version = "1.0.0"

    inputs = [
        Port(
            name="table",
            type=PortType.JSON,
            label="Table",
            description="Structured table data (from Table Extractor)",
            required=True,
        ),
        Port(
            name="question",
            type=PortType.TEXT,
            label="Question",
            description="Question to answer about the table",
            required=True,
        ),
    ]

    outputs = [
        Port(
            name="answer",
            type=PortType.TEXT,
            label="Answer",
            description="Direct answer to the question",
        ),
        Port(
            name="reasoning",
            type=PortType.TEXT,
            label="Reasoning",
            description="Brief explanation of how the answer was derived",
        ),
    ]

    config_fields = [
        ConfigField(
            key="model",
            label="Model",
            type="text",
            required=False,
            default="",
            description="LLM model to use (empty uses default configured model)",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            model = config.get("model", "")

            table: Any = ctx.get_input("table")
            if not table:
                result.fail("No table provided. Connect a Table Extractor node upstream.")
                return result

            question = ctx.get_input("question", "")
            if not isinstance(question, str) or not question.strip():
                result.fail("No question provided via input port")
                return result

            service = TableAgentService(model=model)
            answer = await service.answer(table, question)

            result.succeed({
                "answer": answer["answer"],
                "reasoning": answer["reasoning"],
            })

        except Exception as e:
            result.fail(str(e))

        return result