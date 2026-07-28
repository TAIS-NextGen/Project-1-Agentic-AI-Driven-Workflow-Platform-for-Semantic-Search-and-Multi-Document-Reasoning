from __future__ import annotations

from typing import Any


class EmbeddingService:
    """Generates vector embeddings for text chunks using a local
    sentence-transformers model (bge or e5 family, self-hostable)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    async def embed(self, chunks: list[str]) -> dict[str, Any]:
        model = self._get_model()

        vectors = model.encode(chunks, normalize_embeddings=True)

        embeddings = [
            {
                "chunk": chunk,
                "vector": vector.tolist(),
            }
            for chunk, vector in zip(chunks, vectors)
        ]

        return {
            "embeddings": embeddings,
            "dimension": len(vectors[0]) if len(vectors) > 0 else 0,
            "model": self.model_name,
        }