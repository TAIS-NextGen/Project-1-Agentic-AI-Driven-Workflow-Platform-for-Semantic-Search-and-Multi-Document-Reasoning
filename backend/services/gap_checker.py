from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from backend.schemas.gap_checker import GapReport, GapScore, GapFieldDetail, LLMFieldResponse
from backend.services.llm import LLMService

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "nodes" / "checking" / "templates"

DETERMINISTIC_SYSTEM_PROMPT = """You are a strict compliance auditor. You MUST compare the [Target Document] against a specific requirement.

CRITICAL RULE: If the requirement is NOT explicitly and unambiguously fulfilled in the document, mark it as NOT FOUND. Never infer, assume, or extrapolate compliance. If the text does not clearly contain what the requirement asks for, answer found=false.

Respond ONLY with a JSON object — no explanation, no markdown, no code blocks:
{"requirement_key": "<key>", "found": true or false, "evidence": "<quote from document or 'not found'>", "severity": "WARNING"}"""


class GapCheckerService:
    def __init__(self):
        self._llm: LLMService | None = None

    def _get_llm(self) -> LLMService:
        if self._llm is None:
            self._llm = LLMService()
        return self._llm

    def load_checklist(self, template_name: str) -> dict[str, Any]:
        path = TEMPLATES_DIR / f"{template_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Checklist template '{template_name}' not found at {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _parse_custom_checklist(raw: Any) -> dict[str, Any]:
        if isinstance(raw, str) and raw.strip():
            data = json.loads(raw)
        elif isinstance(raw, list):
            data = raw
        else:
            data = []
        return {"name": "custom", "description": "Custom checklist", "fields": data}

    def _get_fields(self, checklist: dict[str, Any]) -> list[dict[str, Any]]:
        return checklist.get("fields", [])

    @staticmethod
    def _regex_match_field(text: str, field: dict[str, Any]) -> dict[str, Any] | None:
        pattern = field.get("pattern", "")
        if not pattern:
            return None
        try:
            compiled = re.compile(pattern, re.UNICODE | re.IGNORECASE)
            match = compiled.search(text)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                return {
                    "key": field["key"],
                    "label": field.get("label", field["key"]),
                    "required": field.get("required", False),
                    "status": "MATCHED",
                    "severity": field.get("severity", "WARNING"),
                    "value": value.strip(),
                    "method": "regex",
                    "recommended_action": None,
                }
        except re.error:
            logger.warning(f"Invalid regex pattern for field '{field.get('key')}': {pattern}")
        return None

    async def _semantic_check_field(self, text: str, field: dict[str, Any], language: str = "fr") -> dict[str, Any]:
        key = field["key"]
        label = field.get("label", key)
        description = field.get("description", f"Determine if '{label}' is present in the document.")
        severity = field.get("severity", "WARNING")
        required = field.get("required", False)

        prompt = f"""REQUIREMENT: {label}
DESCRIPTION: {description}

Document language: {language}

TARGET DOCUMENT:
{text[:8000]}"""

        try:
            llm = self._get_llm()
            response_text = await llm.generate(
                prompt=prompt,
                system_prompt=DETERMINISTIC_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=4096,
                disable_thinking=True,
            )
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```", 2)[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            parsed = LLMFieldResponse.model_validate_json(response_text)
            return {
                "key": key,
                "label": label,
                "required": required,
                "status": "MATCHED" if parsed.found else "GAP",
                "severity": parsed.severity or severity,
                "value": parsed.evidence if parsed.found else None,
                "method": "semantic",
                "recommended_action": None if parsed.found else f"Verifier manuellement: {label}",
            }
        except Exception as e:
            logger.warning(f"Semantic check failed for '{key}', retrying once: {e}")
            try:
                llm = self._get_llm()
                response_text = await llm.generate(
                    prompt=prompt,
                    system_prompt=DETERMINISTIC_SYSTEM_PROMPT,
                    temperature=0.0,
                    max_tokens=4096,
                    disable_thinking=True,
                )
                response_text = response_text.strip()
                if response_text.startswith("```"):
                    response_text = response_text.split("```", 2)[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                    response_text = response_text.strip()
                parsed = LLMFieldResponse.model_validate_json(response_text)
                return {
                    "key": key,
                    "label": label,
                    "required": required,
                    "status": "MATCHED" if parsed.found else "GAP",
                    "severity": parsed.severity or severity,
                    "value": parsed.evidence if parsed.found else None,
                    "method": "semantic",
                    "recommended_action": None if parsed.found else f"Verifier manuellement: {label}",
                }
            except Exception as e2:
                logger.error(f"Semantic check failed for '{key}' after retry: {e2}")
                return {
                    "key": key,
                    "label": label,
                    "required": required,
                    "status": "UNEVALUATED",
                    "severity": severity,
                    "value": None,
                    "method": "skipped",
                    "recommended_action": f"LLM evaluation failed for '{label}'. Check Ollama is running.",
                }

    async def check(
        self,
        text: str,
        checklist: dict[str, Any],
        mode: str = "both",
        threshold: float = 0.85,
        language: str = "fr",
    ) -> dict[str, Any]:
        fields = self._get_fields(checklist)
        results: list[GapFieldDetail] = []
        semantic_fields: list[dict[str, Any]] = []

        for field in fields:
            method = field.get("method", "regex")
            if method == "regex" or method not in ("semantic",):
                matched = self._regex_match_field(text, field)
                if matched:
                    results.append(GapFieldDetail(**matched))
                else:
                    field_def = {
                        "key": field["key"],
                        "label": field.get("label", field["key"]),
                        "required": field.get("required", False),
                        "status": "GAP",
                        "severity": field.get("severity", "WARNING"),
                        "value": None,
                        "method": "regex",
                        "recommended_action": f"Champ manquant: {field.get('label', field['key'])}",
                    }
                    results.append(GapFieldDetail(**field_def))
            else:
                semantic_fields.append(field)

        if mode in ("semantic", "both"):
            for field in semantic_fields:
                sem_result = await self._semantic_check_field(text, field, language)
                results.append(GapFieldDetail(**sem_result))

        if mode == "deterministic_only":
            for field in semantic_fields:
                results.append(GapFieldDetail(
                    key=field["key"],
                    label=field.get("label", field["key"]),
                    required=field.get("required", False),
                    status="UNEVALUATED",
                    severity=field.get("severity", "WARNING"),
                    value=None,
                    method="skipped",
                    recommended_action=f"Evaluation semantique non disponible en mode deterministic_only",
                ))

        total = len(results)
        matched = sum(1 for r in results if r.status == "MATCHED")
        missing_critical = sum(1 for r in results if r.status in ("GAP",) and r.severity == "CRITICAL")
        missing_warning = sum(1 for r in results if r.status in ("GAP",) and r.severity in ("WARNING", "INFO"))
        percentage = round(matched / total * 100, 1) if total else 100.0
        threshold_met = percentage / 100 >= threshold

        score = GapScore(
            percentage=percentage,
            total_fields=total,
            matched=matched,
            missing_critical=missing_critical,
            missing_warning=missing_warning,
            threshold_exceeded=threshold_met,
        )

        missing_keys = [r.key for r in results if r.status == "GAP" and r.severity == "CRITICAL"]

        report = GapReport(
            fields=results,
            score=score,
            missing=missing_keys,
            has_critical_gaps=missing_critical > 0,
        )

        return report.model_dump()
