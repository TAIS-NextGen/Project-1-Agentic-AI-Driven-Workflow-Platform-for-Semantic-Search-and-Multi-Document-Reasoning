from __future__ import annotations

from abc import abstractmethod
from typing import Any, Callable

from .base_node import BaseNode
from .config import ConfigField
from .context import ExecutionContext
from .ports import Port, PortType
from .result import NodeResult, NodeStatus


class BaseAgent(BaseNode):
    max_iterations: int = 10
    system_prompt: str = ""
    tools: list[Callable] = []

    inputs: list[Port] = [
        Port("prompt", PortType.TEXT, "Prompt", "The input prompt for the agent"),
    ]
    outputs: list[Port] = [
        Port("response", PortType.TEXT, "Response", "The agent's response"),
    ]

    config_fields: list[ConfigField] = [
        ConfigField(key="model", label="Model", type="select",
                    options=["gpt-4o", "gpt-4o-mini", "claude-3-opus", "claude-3-sonnet"],
                    default="gpt-4o", required=True),
        ConfigField(key="temperature", label="Temperature", type="slider",
                    default=0.7, description="Creativity vs determinism (0-1)"),
        ConfigField(key="max_tokens", label="Max Tokens", type="number",
                    default=4096, description="Maximum response length"),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            prompt = ctx.get_input("prompt", "")
            resolved_config = self.get_resolved_config()

            response = await self.run_agent_loop(ctx, prompt, resolved_config)

            result.succeed({"response": response})
        except Exception as e:
            result.fail(str(e))

        return result

    @abstractmethod
    async def run_agent_loop(
        self,
        ctx: ExecutionContext,
        prompt: str,
        config: dict[str, Any],
    ) -> str:
        ...
