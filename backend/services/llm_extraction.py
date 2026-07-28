from __future__ import annotations

import json as json_lib
import logging
import re
from pathlib import Path
from typing import Any

from backend.services.llm import LLMService

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "nodes" / "extraction" / "templates"

EXTRACTION_SYSTEM_PROMPT = """You are a precise document data extractor. Extract the requested fields from the document text below.

CRITICAL RULES:
1. Return ONLY valid JSON — no explanation, no markdown, no code blocks.
2. If a field is not found in the document, set its value to null.
3. If a field expects an array (e.g. line items), return an empty array if none found.
4. Normalize dates to YYYY-MM-DD format when possible.
5. Don't invent or hallucinate values — if the document doesn't say it, use null.
6. For amounts, extract just the numeric value (no currency symbols).
7. Return the JSON object directly, no wrapping.
8. For reference numbers (invoice, facture, bon, commande): scan the text near keywords like 'Facture', 'N°', 'Numero', 'Ref', 'No'. The identifier often appears right after these keywords on the same line, sometimes separated by ':' or ':'. Examples: 'Facture N°: FACT-2026-0842' -> 'FACT-2026-0842', 'N° INV-1234' -> 'INV-1234'."""


class LLMExtractionService:
    def __init__(self, model: str = ""):
        self._llm: LLMService | None = None
        self._model = model

    def _get_llm(self) -> LLMService:
        if self._llm is None:
            self._llm = LLMService(model=self._model) if self._model else LLMService()
        return self._llm

    def load_template(self, template_name: str) -> dict[str, Any]:
        path = TEMPLATES_DIR / f"{template_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Template '{template_name}' not found at {path}")
        return json_lib.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _parse_fields(raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, str) and raw.strip():
            return json_lib.loads(raw)
        if isinstance(raw, list):
            return raw
        return []

    def _build_fields_section(self, fields: list[dict[str, Any]]) -> str:
        lines = []
        for f in fields:
            key = f.get("key", f.get("name", ""))
            label = f.get("label", key)
            desc = f.get("description", f"Extract the {label}")
            ftype = f.get("type", "string")
            type_hint = f" (type: {ftype})" if ftype != "string" else ""
            lines.append(f"- {key}: {desc}{type_hint}")
        return "\n".join(lines)

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            blocks = text.split("```")
            for i in range(1, len(blocks), 2):
                candidate = blocks[i].strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                return candidate
        brace_start = text.find("{")
        if brace_start >= 0:
            return text[brace_start:]
        return text

    @staticmethod
    def _validate_field(value: Any, field_def: dict[str, Any]) -> tuple[Any, float]:
        if value is None or value == "":
            return None, 0.0

        ftype = field_def.get("type", "string")
        confidence = 0.9

        if ftype == "number":
            try:
                value = float(value) if "." in str(value) else int(value)
            except (ValueError, TypeError):
                confidence = 0.3
        elif ftype == "array":
            if not isinstance(value, list):
                confidence = 0.2

        return value, confidence

    def _build_output_schema(self, fields: list[dict[str, Any]]) -> str:
        schema = {}
        for f in fields:
            key = f.get("key", f.get("name", ""))
            schema[key] = None
        return json_lib.dumps(schema, indent=2, ensure_ascii=False)

    async def extract(
        self,
        text: str,
        fields: list[dict[str, Any]],
        language: str = "fr",
    ) -> dict[str, Any]:
        text = re.sub(r"\bN\u00b0\b", "No", text)
        text = re.sub(r"\n\s*\}\s*\d*\s*$", "", text)

        fields_section = self._build_fields_section(fields)
        output_schema = self._build_output_schema(fields)
        language_hint = f"\nDocument language: {language}." if language else ""

        prompt = f"""Extract the following fields from this document.{language_hint}

FIELDS TO EXTRACT:
{fields_section}

Return ONLY this exact JSON structure (use null for missing fields):
{output_schema}

DOCUMENT TEXT:
{text[:12000]}"""

        llm = self._get_llm()
        response_text = await llm.generate(
            prompt=prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=4096,
            disable_thinking=True,
        )

        json_str = self._extract_json(response_text)

        try:
            extracted = json_lib.loads(json_str)
        except json_lib.JSONDecodeError:
            logger.warning(f"Failed to parse LLM JSON response. Response was: {response_text[:500]}")
            extracted = {}

        result: dict[str, dict[str, Any]] = {}
        for f in fields:
            key = f.get("key", f.get("name", ""))
            if not key:
                continue
            raw_value = extracted.get(key)
            value, confidence = self._validate_field(raw_value, f)
            result[key] = {
                "value": value,
                "confidence": round(confidence, 4),
                "label": f.get("label", key),
                "found": value is not None,
            }

        for f in fields:
            key = f.get("key", f.get("name", ""))
            if not key or result.get(key, {}).get("found"):
                continue
            pattern = f.get("pattern", "")
            if not pattern:
                continue
            match = re.search(pattern, text)
            if match:
                raw = match.group(1) if match.lastindex else match.group(0)
                value, confidence = self._validate_field(raw.strip(), f)
                result[key] = {
                    "value": value,
                    "confidence": round(confidence, 4),
                    "label": f.get("label", key),
                    "found": value is not None,
                }

        matched = sum(1 for v in result.values() if v["found"])
        total = len(result)

        return {
            "extracted": result,
            "stats": {
                "total_fields": total,
                "matched": matched,
                "unmatched": total - matched,
                "match_rate": round(matched / total, 4) if total else 0,
            },
        }
