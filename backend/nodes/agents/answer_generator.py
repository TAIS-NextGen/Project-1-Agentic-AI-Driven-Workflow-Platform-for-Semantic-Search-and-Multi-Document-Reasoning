from __future__ import annotations

import json as json_lib
from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)
from backend.services.answer_generator import AnswerGeneratorService


class AnswerGeneratorNode(BaseNode):
    type = "answer-generator"
    name = "Answer Generator Agent"
    category = "agents"
    icon = "💬"
    color = "#a855f7"
    description = "Produce the final readable answer from agent results and evidence"
    version = "1.0.0"

    inputs = [
        Port(
            name="question",
            type=PortType.TEXT,
            label="Question",
            description="Original user question",
            required=True,
        ),
        Port(
            name="agent_results",
            type=PortType.JSON,
            label="Agent Results",
            description="Combined outputs from upstream agents (Table Agent, Text Reasoning, etc.)",
            required=True,
        ),
        Port(
            name="evidence",
            type=PortType.JSON,
            label="Evidence",
            description="Supporting evidence used by the agents",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="answer",
            type=PortType.TEXT,
            label="Final Answer",
            description="Synthesized, human-readable final answer",
        ),
        Port(
            name="confidence",
            type=PortType.TEXT,
            label="Confidence",
            description="Confidence level: high, medium, or low",
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
        ConfigField(
            key="question",
            label="Question",
            type="text",
            required=False,
            default="",
            description="User question. Leave empty if provided via upstream connection.",
        ),
        ConfigField(
            key="agent_results",
            label="Agent Results (JSON)",
            type="json",
            required=False,
            default="{}",
            description="Combined outputs from upstream agents as JSON. Leave empty if provided via upstream connection.",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            model = config.get("model", "")

            question = ctx.get_input("question", "") or str(config.get("question", ""))
            if not isinstance(question, str) or not question.strip():
                result.fail("No question provided via input port or config field")
                return result

            agent_results: Any = ctx.get_input("agent_results")
            if not agent_results:
                raw = config.get("agent_results", "{}")
                if isinstance(raw, str) and raw.strip():
                    try:
                        agent_results = json_lib.loads(raw)
                    except (json_lib.JSONDecodeError, TypeError):
                        agent_results = {}
                elif isinstance(raw, dict):
                    agent_results = raw
            if not agent_results:
                result.fail("No agent results provided. Connect upstream agent nodes or provide JSON in config.")
                return result

            evidence: Any = ctx.get_input("evidence")

            service = AnswerGeneratorService(model=model)
            generated = await service.generate(question, agent_results, evidence)

            result.succeed({
                "answer": generated["answer"],
                "confidence": generated["confidence"],
            })

        except Exception as e:
            result.fail(str(e))

        return result