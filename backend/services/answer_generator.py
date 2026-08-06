from __future__ import annotations

import json
import logging
from typing import Any

from backend.services.llm import LLMService

logger = logging.getLogger(__name__)

ANSWER_GENERATOR_SYSTEM_PROMPT = """You are the final answer-generation step in a \
document-analysis pipeline. You are given the outputs from one or more specialized \
agents (table reasoning, text reasoning, image analysis, etc.) along with supporting \
evidence, and the original user question.

RULES:
1. Synthesize a single, clear, human-readable answer to the original question.
2. Base the answer only on the provided agent results and evidence — do not invent facts.
3. If the agent results conflict or are incomplete, note that briefly in the answer.
4. Respond ONLY with a JSON object, no markdown, no explanation:
   {"answer": "<final readable answer>", "confidence": "high" | "medium" | "low"}"""


class AnswerGeneratorService:
    def __init__(self, model: str = ""):
        self._model = model

    def _get_llm(self) -> LLMService:
        return LLMService(model=self._model)

    async def generate(
        self,
        question: str,
        agent_results: dict[str, Any] | list[Any],
        evidence: dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any]:
        results_text = json.dumps(agent_results)
        evidence_text = json.dumps(evidence) if evidence else "{}"

        prompt = (
            f"Original question: {question}\n\n"
            f"Agent results:\n{results_text}\n\n"
            f"Evidence:\n{evidence_text}\n\n"
            "Produce the final answer."
        )

        llm = self._get_llm()
        raw_response = await llm.generate(
            prompt=prompt,
            system_prompt=ANSWER_GENERATOR_SYSTEM_PROMPT,
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
            logger.warning(f"AnswerGeneratorService: failed to parse LLM response as JSON: {raw_response[:200]}")
            return {"answer": raw_response, "confidence": "low"}

        return {
            "answer": parsed.get("answer", ""),
            "confidence": parsed.get("confidence", "medium"),
        }