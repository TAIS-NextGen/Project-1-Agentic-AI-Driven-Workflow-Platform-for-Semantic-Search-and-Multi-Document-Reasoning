from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import re

import langdetect
from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)


class LanguageDetectorNode(BaseNode):
    type = "language-detector"
    name = "Language Detector"
    category = "extraction"
    icon = "🌐"
    color = "#ec4899"
    description = "Detect the language(s) of a given text. Supports multi-language documents."
    version = "1.0.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Raw text to detect language from",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="languages",
            type=PortType.JSON,
            label="Detected Languages",
            description="List of detected languages with confidence scores",
        ),
        Port(
            name="languages_str",
            type=PortType.TEXT,
            label="Detected Language(s)",
            description="Comma-separated list of detected languages",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID containing text to parse. If empty, expects text from upstream input.",
        ),
        ConfigField(
            key="detection_mode",
            label="Detection Mode",
            type="text",
            required=False,
            default="document",
            description="Granularity: 'document' (entire text), 'paragraph' (per paragraph), or 'sentence' (per sentence)",
        ),
        ConfigField(
            key="min_probability",
            label="Min Probability",
            type="number",
            required=False,
            default=0.1,
            description="Minimum probability threshold to include a language in results",
        ),
        ConfigField(
            key="max_languages",
            label="Max Languages",
            type="number",
            required=False,
            default=5,
            description="Maximum number of unique languages to return",
        ),
        ConfigField(
            key="text",
            label="Text",
            type="text",
            required=False,
            default="",
            description="Text to detect language from. Leave empty if provided via upstream connection.",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            detection_mode = config.get("detection_mode", "document")
            min_prob = float(config.get("min_probability", 0.1))
            max_langs = int(config.get("max_languages", 5))

            text = ctx.get_input("text", "") or str(config.get("text", ""))
            if not isinstance(text, str) or not text.strip():
                file_id = config.get("file_id", "")
                if not file_id:
                    result.fail("No text provided via input port or 'file_id' config")
                    return result
                text = await self._read_text_file(file_id)
                if not text:
                    result.fail(f"No readable text found for file '{file_id}'")
                    return result

            # Segment the text based on selected mode
            segments: list[str] = []
            if detection_mode == "paragraph":
                segments = [p.strip() for p in text.split("\n") if p.strip()]
            elif detection_mode == "sentence":
                # Basic sentence splitting (by period, exclamation, question mark)
                sentences = re.split(r"(?<=[.!?])\s+", text)
                segments = [s.strip() for s in sentences if s.strip()]
            else:
                segments = [text.strip()]

            # Detect languages for each segment
            lang_stats: dict[str, list[float]] = {}
            for seg in segments:
                # langdetect needs enough content to work, skip very short text/numbers
                if len(re.sub(r"[^a-zA-Z]", "", seg)) < 3:
                    continue
                try:
                    detected_langs = langdetect.detect_langs(seg)
                    for dl in detected_langs:
                        if dl.lang not in lang_stats:
                            lang_stats[dl.lang] = []
                        lang_stats[dl.lang].append(dl.prob)
                except Exception:
                    # Ignore segments that fail language detection (e.g. only punctuation, numbers)
                    continue

            # If no languages could be detected, fallback to entire document detection
            if not lang_stats:
                try:
                    detected_langs = langdetect.detect_langs(text)
                    for dl in detected_langs:
                        lang_stats[dl.lang] = [dl.prob]
                except Exception:
                    pass

            # Aggregate probabilities: average of detected probabilities for each language
            aggregated_langs: list[dict[str, Any]] = []
            for lang, probs in lang_stats.items():
                avg_prob = sum(probs) / len(probs)
                if avg_prob >= min_prob:
                    aggregated_langs.append({"lang": lang, "probability": round(avg_prob, 4)})

            # Sort by probability descending
            aggregated_langs.sort(key=lambda x: x["probability"], reverse=True)
            aggregated_langs = aggregated_langs[:max_langs]

            # Construct comma separated string representation
            languages_str = ", ".join([item["lang"] for item in aggregated_langs])

            result.succeed({
                "languages": aggregated_langs,
                "languages_str": languages_str or "unknown",
            })

        except Exception as e:
            result.fail(str(e))

        return result

    async def _read_text_file(self, file_id: str) -> str | None:
        import os

        upload_dir = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
        if not upload_dir.exists():
            return None
        for f in upload_dir.iterdir():
            if f.stem == file_id:
                return f.read_text(encoding="utf-8", errors="replace")
        return None
