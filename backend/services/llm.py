from __future__ import annotations

import logging
from typing import Any

from backend.settings import settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, api_key: str = "", model: str = "", base_url: str = "", **kwargs):
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_default_model
        self.base_url = base_url or settings.llm_base_url
        self.kwargs = kwargs

    def _get_client(self):
        from openai import AsyncOpenAI

        key = self.api_key or "ollama"
        return AsyncOpenAI(api_key=key, base_url=self.base_url or None)

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        disable_thinking: bool = True,
    ) -> str:
        if not self.base_url and not self.api_key:
            logger.warning("LLMService.generate() — no API key or base URL configured, using mock")
            return f"[Mock LLM response for: {prompt[:50]}...]"

        client = self._get_client()
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        extra_body: dict[str, Any] = {}
        if disable_thinking:
            extra_body["enable_thinking"] = False

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body if extra_body else None,
            )
            content = response.choices[0].message.content or ""

            if not content:
                msg = response.choices[0].message
                finish = response.choices[0].finish_reason
                reasoning = getattr(msg, "reasoning_content", None)
                if not reasoning and msg.model_extra:
                    reasoning = msg.model_extra.get("reasoning", "")
                if reasoning:
                    logger.warning(
                        f"Thinking model '{self.model}' spent all tokens on reasoning "
                        f"(finish_reason={finish}). Increase max_tokens or set disable_thinking=True."
                    )
                    content = (
                        "[Error: model produced reasoning but no final answer. "
                        "Increase max_tokens or disable thinking.]"
                    )
                else:
                    logger.warning(
                        f"LLM returned empty content (finish_reason={finish})."
                    )
                    content = ""

            return content
        except Exception as e:
            logger.error(f"LLMService.generate() failed: {e}")
            raise

    async def generate_with_image(
        self,
        prompt: str,
        image_path: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
    ) -> str:
        import base64
        from pathlib import Path

        ext = Path(image_path).suffix.lower()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        client = self._get_client()
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        })

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLMService.generate_with_image() failed: {e}")
            raise

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
