from __future__ import annotations

import base64
import logging
from pathlib import Path
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

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str = "",
        max_iterations: int = 10,
    ) -> tuple[str, list[dict[str, Any]]]:
        logger.warning("LLMService.generate_with_tools() not implemented — using mock")
        return f"[Mock tool-call response for: {prompt[:50]}...]", []

    async def generate_with_image(
        self,
        prompt: str,
        image_path: str = "",
        image_url: str = "",
        system_prompt: str = "",
        max_tokens: int = 1024,
    ) -> str:
        if not self.base_url and not self.api_key:
            logger.warning("LLMService.generate_with_image() — no API key or base URL configured, using mock")
            return f"[Mock vision response for: {prompt[:50]}...]"

        client = self._get_client()

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        if image_path:
            image_path_obj = Path(image_path)
            if image_path_obj.exists():
                with open(image_path_obj, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                ext = image_path_obj.suffix.lower().lstrip(".")
                mime = f"image/{ext}" if ext in ("png", "jpeg", "jpg", "gif", "webp") else "image/jpeg"
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                })
            else:
                logger.error(f"Image not found: {image_path}")
                return f"[Error: image not found at {image_path}]"
        elif image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_url},
            })

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content})

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

    async def embed(self, text: str) -> list[float]:
        result = await self.embed_batch([text])
        return result[0] if result else [0.0] * 384

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not self.base_url and not self.api_key:
            logger.warning("LLMService.embed_batch() — no base URL configured, using mock")
            return [[0.0] * 384 for _ in texts]

        client = self._get_client()
        try:
            response = await client.embeddings.create(model=self.model, input=texts)
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"LLMService.embed_batch() failed: {e}")
            raise
