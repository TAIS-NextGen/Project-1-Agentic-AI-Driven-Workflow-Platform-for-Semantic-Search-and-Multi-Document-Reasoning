# backend/services/normalization.py
from __future__ import annotations

import re
from typing import Any

import dateparser


class TextCleanerService:
    
    _HYPHEN_BREAK_RE = re.compile(r"-\s*\n\s*(?=[a-zà-ÿ])")

    _MULTI_WHITESPACE_RE = re.compile(r"[ \t]+")
    _MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

    _SPECIAL_CHARS_RE = re.compile(r"[^\w\s.,;:!?()\[\]/%€$@'\"-]", re.UNICODE)

    _DATE_CANDIDATE_RE = re.compile(
        r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
        r"|\d{1,2}\s+\w+\s+\d{4}"
        r"|\w+\s+\d{1,2},?\s+\d{4})\b"
    )

    def clean(
        self,
        text: str,
        *,
        fix_hyphenation: bool = True,
        collapse_whitespace: bool = True,
        strip_special_chars: bool = False,
        normalize_casing: str | None = None,  # "lower" | "upper" | "title" | None
        normalize_dates: bool = False,
        date_output_format: str = "%Y-%m-%d",
    ) -> dict[str, Any]:
        original_length = len(text)
        cleaned = text

        if fix_hyphenation:
            cleaned = self._HYPHEN_BREAK_RE.sub("", cleaned)

        if strip_special_chars:
            cleaned = self._SPECIAL_CHARS_RE.sub("", cleaned)

        dates_found: list[dict[str, str]] = []
        if normalize_dates:
            cleaned, dates_found = self._normalize_dates(cleaned, date_output_format)

        if collapse_whitespace:
            cleaned = self._MULTI_NEWLINE_RE.sub("\n\n", cleaned)
            cleaned = self._MULTI_WHITESPACE_RE.sub(" ", cleaned)
            cleaned = "\n".join(line.strip() for line in cleaned.split("\n"))
            cleaned = cleaned.strip()

        if normalize_casing == "lower":
            cleaned = cleaned.lower()
        elif normalize_casing == "upper":
            cleaned = cleaned.upper()
        elif normalize_casing == "title":
            cleaned = cleaned.title()

        return {
            "cleaned_text": cleaned,
            "stats": {
                "original_length": original_length,
                "cleaned_length": len(cleaned),
                "chars_removed": original_length - len(cleaned),
                "dates_normalized": len(dates_found),
            },
            "dates": dates_found,
        }

    def _normalize_dates(
        self, text: str, output_format: str
    ) -> tuple[str, list[dict[str, str]]]:
        found: list[dict[str, str]] = []

        def _replace(match: re.Match) -> str:
            raw = match.group(0)
            parsed = dateparser.parse(raw)
            if parsed is None:
                return raw
            formatted = parsed.strftime(output_format)
            found.append({"original": raw, "normalized": formatted})
            return formatted

        result = self._DATE_CANDIDATE_RE.sub(_replace, text)
        return result, found