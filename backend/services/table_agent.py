from __future__ import annotations

import json
import logging
from typing import Any

from backend.services.llm import LLMService

logger = logging.getLogger(__name__)

TABLE_AGENT_SYSTEM_PROMPT = """You are a table-reasoning assistant. You are given a \
structured table (rows and columns) and a question about it.

RULES:
1. Reason over the table data to answer the question — perform lookups, aggregations \
(sums, averages, counts, comparisons) as needed.
2. Base your answer only on the table's actual data. Do not invent values.
3. Respond ONLY with a JSON object, no markdown, no explanation:
   {"answer": "<direct answer>", "reasoning": "<brief explanation of how you got there>"}"""


class TableAgentService:
    def __init__(self, model: str = ""):
        self._model = model

    def _get_llm(self) -> LLMService:
        return LLMService(model=self._model)

    async def answer(self, table: dict[str, Any] | list[Any], question: str) -> dict[str, Any]:
        table_text = json.dumps(table)

        prompt = f"Table:\n{table_text}\n\nQuestion: {question}"

        llm = self._get_llm()
        raw_response = await llm.generate(
            prompt=prompt,
            system_prompt=TABLE_AGENT_SYSTEM_PROMPT,
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
            logger.warning(f"TableAgentService: failed to parse LLM response as JSON: {raw_response[:200]}")
            return {"answer": raw_response, "reasoning": ""}

        return {
            "answer": parsed.get("answer", ""),
            "reasoning": parsed.get("reasoning", ""),
        }