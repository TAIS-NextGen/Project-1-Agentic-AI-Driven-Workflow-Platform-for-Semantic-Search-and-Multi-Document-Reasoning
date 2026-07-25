from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class VectorDBService:
    def __init__(self, connection_url: str = "", collection_name: str = "default"):
        self.connection_url = connection_url
        self.collection_name = collection_name

    async def upsert(self, vectors: list[list[float]], payloads: list[dict[str, Any]], ids: list[str]) -> None:
        logger.warning("VectorDBService.upsert() not implemented — using mock")

    async def search(self, vector: list[float], top_k: int = 10) -> list[dict[str, Any]]:
        logger.warning("VectorDBService.search() not implemented — using mock")
        return [
            {"id": f"mock-{i}", "score": 1.0 - (i * 0.1), "payload": {"text": f"Mock result {i}"}}
            for i in range(top_k)
        ]

    async def delete_collection(self) -> None:
        logger.warning("VectorDBService.delete_collection() not implemented — using mock")

    async def collection_info(self) -> dict[str, Any]:
        return {
            "name": self.collection_name,
            "vector_count": 0,
            "connected": bool(self.connection_url),
        }
