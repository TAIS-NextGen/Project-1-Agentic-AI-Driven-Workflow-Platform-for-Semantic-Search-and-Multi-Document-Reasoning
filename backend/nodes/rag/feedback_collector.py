from __future__ import annotations

import json as json_lib
import logging
import os
import uuid
from datetime import datetime, timezone
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
from backend.services.llm import LLMService

logger = logging.getLogger(__name__)

CATEGORIZATION_SYSTEM_PROMPT = """You are a feedback classifier for a RAG system.
Categorize the user correction about an answer.
Respond ONLY with a valid JSON object — no explanation, no markdown.

Categories:
- hallucination: the answer invented false or wrong facts
- incomplete: the answer missed information that was asked
- irrelevant: the answer is off-topic or used wrong context
- corrected: the user provided a corrected version of the answer
- other: does not fit any of the above

Return: {"category": "<category>", "explanation": "<one short sentence in French>"}"""


class FeedbackCollectorNode(BaseNode):
    type = "feedback-collector"
    name = "Feedback Collector"
    category = "rag"
    icon = "\U0001f4ca"
    color = "#f43f5e"
    description = "Collecter le feedback utilisateur pour ameliorer le RAG"
    version = "1.0.0"

    inputs = [
        Port(
            name="question",
            type=PortType.TEXT,
            label="Question",
            description="Original user question",
        ),
        Port(
            name="answer",
            type=PortType.TEXT,
            label="Answer",
            description="LLM-generated answer that was shown to the user",
        ),
        Port(
            name="chunks_used",
            type=PortType.JSON,
            label="Chunks Used",
            description="Chunks that were provided to the LLM for context",
            required=False,
        ),
        Port(
            name="feedback",
            type=PortType.JSON,
            label="User Feedback",
            description='{"sentiment": "positive"|"negative", "correction": "..."}',
        ),
    ]

    outputs = [
        Port(
            name="signal",
            type=PortType.JSON,
            label="Feedback Signal",
            description="Structured signal with category and improvement suggestion",
        ),
        Port(
            name="stored",
            type=PortType.JSON,
            label="Storage Confirmation",
            description="Entry ID, timestamp and file path",
        ),
    ]

    config_fields = [
        ConfigField(
            key="storage_path",
            label="Storage Path",
            type="text",
            required=False,
            default="data/feedback",
            description="Directory where feedback entries are stored",
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
            key="answer",
            label="Answer",
            type="text",
            required=False,
            default="",
            description="Generated answer to evaluate. Leave empty if provided via upstream connection.",
        ),
        ConfigField(
            key="feedback",
            label="Feedback (JSON)",
            type="json",
            required=False,
            default='{"sentiment":"positive","correction":""}',
            description='User feedback: {"sentiment":"positive"|"negative","correction":"..."}',
        ),
    ]

    def _get_storage_dir(self) -> Path:
        config = self._config or {}
        raw = config.get("storage_path", "data/feedback")
        return Path(raw)

    @staticmethod
    def _validate_feedback(feedback: dict[str, Any] | None) -> str | None:
        if not feedback:
            return "The 'feedback' input is required"
        sentiment = feedback.get("sentiment", "")
        if sentiment not in ("positive", "negative"):
            return "Feedback sentiment must be 'positive' or 'negative'"
        if sentiment == "negative":
            correction = feedback.get("correction", "")
            if not correction or not correction.strip():
                return "Correction is required for negative feedback. The user must explain what was wrong."
        return None

    async def _categorize_with_llm(
        self,
        question: str,
        answer: str,
        correction: str,
    ) -> dict[str, str]:
        prompt = (
            f"Categorize this correction about a RAG answer.\n\n"
            f"Question: {question}\n"
            f"Original answer: {answer}\n"
            f"User correction: {correction}\n\n"
            f"Return: {{\"category\": \"<category>\", \"explanation\": \"<one short sentence in French>\"}}"
        )

        llm = LLMService()
        response_text = await llm.generate(
            prompt=prompt,
            system_prompt=CATEGORIZATION_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=256,
            disable_thinking=True,
        )

        response_text = response_text.strip()
        if response_text.startswith("```"):
            blocks = response_text.split("```")
            for i in range(1, len(blocks), 2):
                candidate = blocks[i].strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                response_text = candidate
                break

        try:
            parsed = json_lib.loads(response_text)
            return {
                "category": parsed.get("category", "other"),
                "explanation": parsed.get("explanation", "No explanation provided"),
            }
        except (json_lib.JSONDecodeError, KeyError):
            logger.warning(f"Failed to parse LLM categorization response: {response_text[:200]}")
            return {"category": "other", "explanation": response_text[:200]}

    def _store_entry(self, entry: dict[str, Any]) -> Path:
        storage_dir = self._get_storage_dir()
        storage_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"feedback_{date_str}.jsonl"
        filepath = storage_dir / filename

        line = json_lib.dumps(entry, ensure_ascii=False) + "\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line)

        logger.info(f"Feedback entry {entry['entry_id']} stored at {filepath}")
        return filepath

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            question = ctx.get_input("question", "") or str(config.get("question", ""))
            answer = ctx.get_input("answer", "") or str(config.get("answer", ""))
            chunks_used = ctx.get_input("chunks_used", [])
            feedback = ctx.get_input("feedback", {})
            if not feedback:
                raw_feedback = config.get("feedback", "{}")
                if isinstance(raw_feedback, str) and raw_feedback.strip():
                    try:
                        feedback = json_lib.loads(raw_feedback)
                    except (json_lib.JSONDecodeError, TypeError):
                        feedback = {}
                elif isinstance(raw_feedback, dict):
                    feedback = raw_feedback

            if not question or not question.strip():
                result.fail("The 'question' input is required")
                return result
            if not answer or not answer.strip():
                result.fail("The 'answer' input is required")
                return result

            validation_error = self._validate_feedback(feedback)
            if validation_error:
                result.fail(validation_error)
                return result

            sentiment = feedback["sentiment"]
            correction = feedback.get("correction", "")

            if sentiment == "positive":
                category = "positive"
                explanation = ""
            else:
                llm_result = await self._categorize_with_llm(question, answer, correction)
                category = llm_result["category"]
                explanation = llm_result["explanation"]

            entry_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()

            entry = {
                "entry_id": entry_id,
                "timestamp": timestamp,
                "question": question,
                "answer": answer,
                "chunks_used": chunks_used if chunks_used else None,
                "sentiment": sentiment,
                "correction": correction if correction else None,
                "category": category,
                "explanation": explanation if explanation else None,
            }

            filepath = self._store_entry(entry)

            status = "positive" if category == "positive" else "needs_fix"

            signal = {
                "status": status,
                "category": category,
                "explanation": explanation if explanation else None,
                "has_correction": bool(correction and correction.strip()),
                "timestamp": timestamp,
            }

            stored = {
                "entry_id": entry_id,
                "timestamp": timestamp,
                "path": str(filepath),
            }

            result.succeed({"signal": signal, "stored": stored})

        except Exception as e:
            result.fail(str(e))

        return result
