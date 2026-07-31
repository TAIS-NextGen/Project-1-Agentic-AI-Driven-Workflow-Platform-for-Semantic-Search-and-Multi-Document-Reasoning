from __future__ import annotations

import json as json_lib
import logging
from typing import Any

from backend.services.llm import LLMService

logger = logging.getLogger(__name__)

SENTIMENT_SYSTEM_PROMPT = """You are an expert sentiment and tone analyzer. Analyze the provided text and return a structured JSON response.

CRITICAL RULES:
1. Return ONLY valid JSON — no explanation, no markdown, no code blocks.
2. For sentiment analysis: determine polarity (positive, negative, neutral), assign a score from -1.0 (very negative) to 1.0 (very positive), and a confidence score from 0.0 to 1.0.
3. For tone analysis: identify the primary tone (formal, informal, urgent, persuasive, informative, emotional, technical, conversational, assertive, passive, optimistic, pessimistic, angry, sad, joyful, concerned, neutral), list up to 3 secondary tones with individual scores, and provide an intensity score from -1.0 (very mild) to 1.0 (very intense).
4. For the summary: write a brief natural-language summary of the overall sentiment and tone in the requested language.
5. Don't invent or hallucinate — be honest about uncertainty (use lower confidence).
6. Return the JSON object directly, no wrapping.

SCORING GUIDELINES:
- Sentiment score: -1.0 = very negative, -0.5 = somewhat negative, 0.0 = neutral, 0.5 = somewhat positive, 1.0 = very positive
- Tone intensity: -1.0 = very mild/subtle tone, 0.0 = moderate tone, 1.0 = very intense/strong tone
- Confidence: 0.0-0.3 = highly uncertain, 0.4-0.6 = moderately confident, 0.7-1.0 = highly confident"""


class SentimentAnalyzerService:
    def __init__(self, model: str = ""):
        self._llm: LLMService | None = None
        self._model = model

    def _get_llm(self) -> LLMService:
        if self._llm is None:
            self._llm = LLMService(model=self._model) if self._model else LLMService()
        return self._llm

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

    async def analyze(
        self,
        text: str,
        language: str = "fr",
        analysis_type: str = "both",
        detail_level: str = "detailed",
    ) -> dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("No text provided for sentiment analysis")

        language_map = {
            "fr": "French",
            "en": "English",
            "ar": "Arabic",
        }
        lang_name = language_map.get(language, language)

        detail_hint = ""
        if detail_level == "basic":
            detail_hint = "Keep secondary_tone analysis minimal (1 additional tone max)."
        else:
            detail_hint = "Provide thorough secondary_tone analysis (up to 3 secondary tones)."

        sentiment_request = ""
        tone_request = ""
        if analysis_type == "sentiment_only":
            sentiment_request = "Analyze ONLY the sentiment. Set tone fields to null."
            tone_request = ""
        elif analysis_type == "tone_only":
            sentiment_request = "Set sentiment fields to null."
            tone_request = "Analyze ONLY the tone."
        else:
            sentiment_request = "Analyze the sentiment."
            tone_request = "Analyze the tone."

        prompt = f"""Analyze the following text. Language: {lang_name}.

{sentiment_request}
{tone_request}
{detail_hint}

Return EXACTLY this JSON structure:

{{
  "sentiment": {{
    "polarity": "positive" or "negative" or "neutral",
    "score": number between -1.0 and 1.0,
    "confidence": number between 0.0 and 1.0
  }},
  "tone": {{
    "primary_tone": "informal" or "formal" or "urgent" etc.,
    "secondary_tones": [{{"tone": "...", "score": number between 0.0 and 1.0}}],
    "intensity": number between -1.0 and 1.0,
    "confidence": number between 0.0 and 1.0
  }},
  "summary": "Brief summary of the overall sentiment and tone in {lang_name}."
}}

TEXT TO ANALYZE:
{text[:8000]}"""

        llm = self._get_llm()
        response_text = await llm.generate(
            prompt=prompt,
            system_prompt=SENTIMENT_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=2048,
            disable_thinking=True,
        )

        json_str = self._extract_json(response_text)

        try:
            result = json_lib.loads(json_str)
        except json_lib.JSONDecodeError:
            logger.warning(f"Failed to parse sentiment LLM JSON response. Response was: {response_text[:500]}")
            result = {}

        sentiment = result.get("sentiment") or {}
        tone = result.get("tone") or {}
        summary = result.get("summary", "")

        return {
            "sentiment": {
                "polarity": sentiment.get("polarity", "neutral"),
                "score": sentiment.get("score", 0.0),
                "confidence": sentiment.get("confidence", 0.0),
            },
            "tone": {
                "primary_tone": tone.get("primary_tone", "neutral"),
                "secondary_tones": tone.get("secondary_tones", []),
                "intensity": tone.get("intensity", 0.0),
                "confidence": tone.get("confidence", 0.0),
            },
            "summary": summary,
        }
