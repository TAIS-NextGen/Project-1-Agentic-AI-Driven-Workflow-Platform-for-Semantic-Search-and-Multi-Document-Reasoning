from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, api_key: str = "", model: str = "gpt-4o", **kwargs):
        self.api_key = api_key
        self.model = model
        self.kwargs = kwargs

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        logger.warning("LLMService.generate() not implemented — using mock")
        return f"[Mock LLM response for: {prompt[:50]}...]"

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str = "",
        max_iterations: int = 10,
    ) -> tuple[str, list[dict[str, Any]]]:
        logger.warning("LLMService.generate_with_tools() not implemented — using mock")
        return f"[Mock tool-call response for: {prompt[:50]}...]", []

    async def embed(self, text: str) -> list[float]:
        logger.warning("LLMService.embed() not implemented — using mock")
        return [0.0] * 1536
