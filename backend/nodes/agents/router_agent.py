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
from backend.services.router_agent import RouterAgentService


class RouterAgentNode(BaseNode):
    type = "router-agent"
    name = "Router Agent"
    category = "agents"
    icon = "🧭"
    color = "#a855f7"
    description = "Choose which agents/tools execute a task plan, and in what order"
    version = "1.0.0"

    inputs = [
        Port(
            name="plan",
            type=PortType.JSON,
            label="Task Plan",
            description="Task plan produced by the Planner Agent",
            required=True,
        ),
        Port(
            name="document_structure",
            type=PortType.JSON,
            label="Document Structure",
            description="Document structure map (from Document Structure Analyzer)",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="steps",
            type=PortType.JSON,
            label="Execution Steps",
            description="Ordered list of {order, agent, reason} routing decisions",
        ),
    ]

    config_fields = [
        ConfigField(
            key="model",
            label="Model",
            type="text",
            required=False,
            default="",
            description="LLM model to use for routing decisions (empty uses default configured model)",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            model = config.get("model", "")

            plan: dict[str, Any] | None = ctx.get_input("plan")
            if not plan:
                result.fail("No task plan provided. Connect a Planner Agent node upstream.")
                return result

            document_structure: dict[str, Any] | None = ctx.get_input("document_structure")

            service = RouterAgentService(model=model)
            routing = await service.route(plan, document_structure)

            result.succeed({"steps": routing["steps"]})

        except Exception as e:
            result.fail(str(e))

        return result