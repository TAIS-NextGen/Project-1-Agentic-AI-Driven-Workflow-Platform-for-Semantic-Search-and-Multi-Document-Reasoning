from __future__ import annotations

import json
import logging
from typing import Any

from backend.services.llm import LLMService

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """You are a routing agent in a document-analysis workflow. \
Given a task plan and the document's structure, decide which specialized agents/tools \
should execute each step, and in what order.

Available agents/tools:
- table_agent: reasons over structured tables
- text_reasoning_agent: reasons over plain text chunks, explanations, facts
- image_agent: analyzes figures, diagrams, charts, images
- comparison_agent: compares multiple documents or sources
- summarizer: produces summaries
- translator: translates text
- ocr_node: extracts text from scanned/printed content
- table_extractor: extracts table structure from a page image

RULES:
1. Only select agents/tools that are relevant to the plan and available document structure.
2. Preserve a logical execution order (dependencies first).
3. Respond ONLY with a JSON object, no markdown, no explanation:
   {"steps": [{"order": 1, "agent": "<agent_name>", "reason": "<short reason>"}, ...]}
4. If nothing in the plan matches an available agent, return {"steps": []}."""


class RouterAgentService:
    def __init__(self, model: str = ""):
        self._model = model

    def _get_llm(self) -> LLMService:
        return LLMService(model=self._model)

    async def route(self, plan: dict[str, Any] | str, document_structure: dict[str, Any] | None = None) -> dict[str, Any]:
        plan_text = json.dumps(plan) if not isinstance(plan, str) else plan
        structure_text = json.dumps(document_structure) if document_structure else "{}"

        prompt = (
            f"Task plan:\n{plan_text}\n\n"
            f"Document structure:\n{structure_text}\n\n"
            "Decide which agents should execute this plan, in order."
        )

        llm = self._get_llm()
        raw_response = await llm.generate(
            prompt=prompt,
            system_prompt=ROUTER_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=1024,
        )

        return self._parse_response(raw_response)

    def _parse_response(self, raw_response: str) -> dict[str, Any]:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"RouterAgentService: failed to parse LLM response as JSON: {raw_response[:200]}")
            return {"steps": [], "raw_response": raw_response}

        steps = parsed.get("steps", [])
        if not isinstance(steps, list):
            steps = []

        return {"steps": steps}