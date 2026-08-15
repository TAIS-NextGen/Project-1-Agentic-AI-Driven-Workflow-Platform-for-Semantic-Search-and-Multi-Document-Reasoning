from __future__ import annotations

import re
from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+")


class TextCorrectorNode(BaseNode):
    type = "text-corrector"
    name = "Text Corrector"
    category = "normalization"
    icon = "\u2728"
    color = "#22c55e"
    description = "Fix OCR typos (misspelled words) using a local spell-check dictionary"
    version = "1.0.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Raw OCR text to correct",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="corrected_text",
            type=PortType.TEXT,
            label="Corrected Text",
            description="Text with OCR spelling errors fixed",
        ),
        Port(
            name="changes",
            type=PortType.JSON,
            label="Changes",
            description="Number of corrections applied",
        ),
    ]

    config_fields = [
        ConfigField(
            key="text",
            label="Text",
            type="text",
            required=False,
            default="",
            description="Text to correct. Leave empty if provided via upstream connection.",
        ),
        ConfigField(
            key="language",
            label="Language",
            type="text",
            required=False,
            default="en",
            description="Spell-check dictionary language (en, es, fr, de, ...)",
        ),
        ConfigField(
            key="max_edit_distance",
            label="Max Edit Distance",
            type="number",
            required=False,
            default=1,
            description="Maximum edit distance for a word to be considered misspelled (1 = safe, fixes only single-character errors)",
        ),
    ]

    def _get_checker(self, language: str):
        from spellchecker import SpellChecker

        return SpellChecker(language=language)

    def _correct_word(self, checker, word: str, max_dist: int) -> str:
        # Preserve case style
        if word.isupper():
            style = "upper"
            lower = word.lower()
        elif word[0].isupper() and word[1:].islower():
            style = "title"
            lower = word.lower()
        else:
            style = "lower"
            lower = word.lower()

        # Skip short all-uppercase words (likely acronyms: ITC, USA, IBM, NSDA, FMCG)
        if style == "upper" and len(lower) <= 4:
            return word

        candidates = checker.candidates(lower)
        if not candidates:
            return word  # unknown proper noun — leave as-is
        best = checker.correction(lower)
        if best is None or best == lower:
            return word

        # Compute edit distance; skip if too far (avoid over-correction)
        try:
            from spellchecker import SpellChecker
        except Exception:
            pass
        dist = self._edit_distance(lower, best)
        if dist > max_dist:
            return word

        if style == "upper":
            return best.upper()
        if style == "title":
            return best.capitalize()
        return best

    @staticmethod
    def _edit_distance(a: str, b: str) -> int:
        m, n = len(a), len(b)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev = dp[0]
            dp[0] = i
            for j in range(1, n + 1):
                temp = dp[j]
                cost = 0 if a[i - 1] == b[j - 1] else 1
                dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
                prev = temp
        return dp[n]

    def _merge_split_words(self, checker, text: str) -> tuple[str, int]:
        """Merge adjacent word fragments whose concatenation forms a valid
        dictionary word. E.g. 'WASH NGTON' -> 'WASHINGTON'. Returns
        (merged_text, number_of_merges)."""
        merges = 0
        words = text.split()
        if len(words) < 2:
            return text, 0

        merged: list[str] = []
        i = 0
        while i < len(words):
            if i + 1 < len(words):
                a, b = words[i], words[i + 1]
                combined = a + b
                a_known = bool(checker.known([a.lower()]))
                b_known = bool(checker.known([b.lower()]))
                combined_known = bool(checker.known([combined.lower()]))
                # Merge only if at least one fragment is unknown and the
                # concatenation is a valid dictionary word.
                if (not a_known or not b_known) and combined_known:
                    if a.isupper() and b.isupper():
                        merged.append(combined.upper())
                    else:
                        merged.append(combined)
                    merges += 1
                    i += 2
                    continue
            merged.append(words[i])
            i += 1

        # Rejoin, preserving the original whitespace runs as much as possible.
        result = text
        if merges:
            result = " ".join(merged)
        return result, merges

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            language = config.get("language", "en")
            max_dist = int(config.get("max_edit_distance", 1))

            text = ctx.get_input("text", "") or str(config.get("text", ""))
            if not isinstance(text, str) or not text.strip():
                result.fail("No text provided via input port or 'text' config field")
                return result

            checker = self._get_checker(language)

            corrections = 0

            def _replace(match: re.Match) -> str:
                nonlocal corrections
                word = match.group(0)
                corrected = self._correct_word(checker, word, max_dist)
                if corrected != word:
                    corrections += 1
                return corrected

            corrected_text = _WORD_RE.sub(_replace, text)

            # Split-word merging: fix "WASH NGTON" -> "WASHINGTON" by merging
            # adjacent fragments whose concatenation is a known dictionary word.
            corrected_text, merges = self._merge_split_words(checker, corrected_text)
            corrections += merges

            result.succeed({
                "corrected_text": corrected_text,
                "changes": {
                    "corrections_applied": corrections,
                    "original_chars": len(text),
                    "corrected_chars": len(corrected_text),
                    "engine": "pyspellchecker",
                },
            })

        except Exception as e:
            result.fail(f"Text corrector failed: {e}")

        return result
