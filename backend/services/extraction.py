from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "nodes" / "extraction" / "templates"


class RegexExtractionService:
    def __init__(self, language: str = "fr"):
        self.language = language

    def load_template(self, template_name: str) -> dict[str, Any]:
        path = TEMPLATES_DIR / f"{template_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Template '{template_name}' not found at {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _is_nearby(text: str, pos: int, ctx_re: re.Pattern, max_distance: int = 80) -> bool:
        start = max(0, pos - max_distance)
        end = min(len(text), pos + max_distance)
        return bool(ctx_re.search(text[start:end]))

    @staticmethod
    def _calculate_confidence(
        value: str,
        context_used: bool,
        validators: dict[str, Any] | None,
    ) -> float:
        if not value:
            return 0.0
        score = 0.8
        if context_used:
            score += 0.1
        if validators:
            score += 0.1
        return min(score, 1.0)

    @staticmethod
    def _validate_value(value: str, validators: dict[str, Any]) -> bool:
        if not validators:
            return True
        min_len = validators.get("min_length")
        max_len = validators.get("max_length")
        exact_len = validators.get("exact_length")
        value_len = len(value.strip())
        if min_len is not None and value_len < min_len:
            return False
        if max_len is not None and value_len > max_len:
            return False
        if exact_len is not None and value_len != exact_len:
            return False
        return True

    def extract(self, text: str, patterns: list[dict[str, Any]]) -> dict[str, Any]:
        extracted: dict[str, dict[str, Any]] = {}
        matched_count = 0
        total_patterns = len(patterns)

        for pdef in patterns:
            name = pdef["name"]
            pattern = pdef.get("pattern", "")
            group = pdef.get("group", 0)
            category = pdef.get("category", "general")
            context_before = pdef.get("context_before")
            validators = pdef.get("validators", {})
            mode = pdef.get("mode", "first")

            if not pattern:
                continue

            try:
                compiled = re.compile(pattern, re.UNICODE | re.IGNORECASE)
            except re.error:
                continue

            matches = list(compiled.finditer(text))

            if not matches:
                cat_sec = extracted.setdefault(category, {})
                cat_sec[name] = {"value": None, "confidence": 0.0, "found": False}
                continue

            ctx_re = None
            if context_before:
                ctx_re = re.compile(context_before, re.UNICODE | re.IGNORECASE)

            selected = None
            context_used = False

            if ctx_re:
                nearby = [m for m in matches if self._is_nearby(text, m.start(), ctx_re)]
                if nearby:
                    selected = nearby[0]
                    context_used = True
                else:
                    selected = matches[0]
            else:
                selected = matches[0]

            if not selected:
                cat_sec = extracted.setdefault(category, {})
                cat_sec[name] = {"value": None, "confidence": 0.0, "found": False}
                continue

            if group <= len(selected.groups()):
                value = selected.group(group) or selected.group(0)
            else:
                value = selected.group(0)

            value = value.strip()

            validators_passed = self._validate_value(value, validators)
            if not validators_passed:
                cat_sec = extracted.setdefault(category, {})
                cat_sec[name] = {"value": value, "confidence": 0.0, "found": False}
                continue

            confidence = self._calculate_confidence(value, context_used, validators)

            cat_sec = extracted.setdefault(category, {})
            cat_sec[name] = {"value": value, "confidence": round(confidence, 4), "found": True}
            matched_count += 1

        missing = []
        for pdef in patterns:
            is_req = pdef.get("required", False)
            cat = pdef.get("category", "general")
            nm = pdef["name"]
            if is_req:
                match_found = extracted.get(cat, {}).get(nm, {}).get("found", False)
                if not match_found:
                    missing.append(nm)

        return {
            "extracted": extracted,
            "missing": missing,
            "stats": {
                "total_patterns": total_patterns,
                "matched": matched_count,
                "unmatched": total_patterns - matched_count,
                "match_rate": round(matched_count / total_patterns, 4) if total_patterns else 0,
            },
        }
