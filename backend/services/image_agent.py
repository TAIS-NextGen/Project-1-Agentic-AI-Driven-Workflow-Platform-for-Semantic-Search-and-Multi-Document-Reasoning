from __future__ import annotations

import logging

from backend.services.llm import LLMService

logger = logging.getLogger(__name__)

IMAGE_AGENT_SYSTEM_PROMPT = """You are a precise image analysis assistant. Analyze the image carefully.

RULES:
1. Describe what you see: objects, text, charts, diagrams, numbers.
2. If there are graphs or charts, extract data points and trends.
3. If there is text, transcribe it accurately.
4. Be detailed but concise. No fluff.
5. Respond directly — no markdown, no code blocks."""


class ImageAgentService:
    def __init__(self, model: str = "moondream:latest"):
        self._model = model

    def _get_llm(self) -> LLMService:
        return LLMService(model=self._model)

    async def analyze(self, image_path: str, question: str, language: str = "en") -> str:
        lang_hint = f"Respond in {language}." if language != "en" else ""
        system = f"{IMAGE_AGENT_SYSTEM_PROMPT}\n{lang_hint}".strip()

        llm = self._get_llm()
        return await llm.generate_with_image(
            prompt=question or "Describe this image in detail.",
            image_path=image_path,
            system_prompt=system,
            max_tokens=1024,
        )
