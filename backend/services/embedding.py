from __future__ import annotations

from typing import Any


class EmbeddingService:
    """Generates vector embeddings for text chunks using a local
    embedding model served via Ollama (e.g. nomic-embed-text, 768-dim)."""

    def __init__(self, model_name: str = "nomic-embed-text"):
        self.model_name = model_name

    async def embed(self, chunks: list[str]) -> dict[str, Any]:
        from backend.services.llm import LLMService

        llm = LLMService(model=self.model_name)
        vectors = await llm.embed_batch(chunks)

        embeddings = [
            {
                "chunk": chunk,
                "vector": vector,
            }
            for chunk, vector in zip(chunks, vectors)
        ]

        return {
            "embeddings": embeddings,
            "dimension": len(vectors[0]) if vectors else 0,
            "model": self.model_name,
        }
