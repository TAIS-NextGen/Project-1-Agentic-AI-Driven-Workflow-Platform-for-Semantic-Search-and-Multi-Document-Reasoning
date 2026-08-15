from __future__ import annotations

import json as json_lib
import logging
import math
from pathlib import Path
from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)

logger = logging.getLogger(__name__)


class VectorStoreNode(BaseNode):
    type = "vector-store"
    name = "Vector Store"
    category = "rag"
    icon = "\U0001f5c4\ufe0f"
    color = "#a855f7"
    description = "Store embeddings and retrieve top-k similar chunks via cosine similarity"
    version = "1.0.0"

    inputs = [
        Port(
            name="embeddings",
            type=PortType.JSON,
            label="Embeddings",
            description="Embedding vectors with their chunks (from Embedding Node)",
            required=False,
        ),
        Port(
            name="chunks",
            type=PortType.JSON,
            label="Chunks",
            description="Text chunks corresponding to the embeddings (from Text Splitter)",
            required=False,
        ),
        Port(
            name="query_embedding",
            type=PortType.JSON,
            label="Query Embedding",
            description="Query vector to search against stored embeddings for retrieval",
            required=False,
        ),
        Port(
            name="filename",
            type=PortType.TEXT,
            label="Filename",
            description="Source filename to attach to stored chunks (persisted to the QA index)",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="stored_count",
            type=PortType.JSON,
            label="Stored Count",
            description="Number of vectors stored",
        ),
        Port(
            name="results",
            type=PortType.JSON,
            label="Retrieval Results",
            description="Top-k retrieved chunks with similarity scores",
        ),
    ]

    config_fields = [
        ConfigField(
            key="collection",
            label="Collection Name",
            type="text",
            required=False,
            default="default",
            description="Collection name for organizing stored vectors",
        ),
        ConfigField(
            key="top_k",
            label="Top K",
            type="number",
            required=False,
            default=5,
            description="Number of most similar chunks to retrieve",
        ),
        ConfigField(
            key="embeddings",
            label="Embeddings (JSON)",
            type="json",
            required=False,
            default="[]",
            description="JSON array of [{vector, chunk_text, chunk_id}]. Leave empty if provided via upstream.",
        ),
        ConfigField(
            key="query_embedding",
            label="Query Embedding (JSON)",
            type="json",
            required=False,
            default="[]",
            description="Query vector as JSON array of floats. Leave empty if provided via upstream.",
        ),
        ConfigField(
            key="chunks",
            label="Chunks (JSON)",
            type="json",
            required=False,
            default="[]",
            description="JSON array of chunk objects with text. Leave empty if provided via upstream.",
        ),
        ConfigField(
            key="filename",
            label="Filename",
            type="text",
            required=False,
            default="",
            description="Source filename to attach to stored chunks. Leave empty if provided via upstream.",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            collection = config.get("collection", "default")
            top_k = int(config.get("top_k", 5))

            embeddings_input = ctx.get_input("embeddings")
            chunks_input = ctx.get_input("chunks")
            query_embedding = ctx.get_input("query_embedding")
            filename = ctx.get_input("filename", "") or str(config.get("filename", ""))

            # Parse embeddings from config if not from upstream
            if not embeddings_input:
                raw = config.get("embeddings", "[]")
                if isinstance(raw, str) and raw.strip():
                    embeddings_input = json_lib.loads(raw)
                elif isinstance(raw, list):
                    embeddings_input = raw

            # Parse chunks from config if not from upstream
            if not chunks_input:
                raw = config.get("chunks", "[]")
                if isinstance(raw, str) and raw.strip():
                    chunks_input = json_lib.loads(raw)
                elif isinstance(raw, list):
                    chunks_input = raw

            # Parse query from config if not from upstream
            if not query_embedding:
                raw = config.get("query_embedding", "[]")
                if isinstance(raw, str) and raw.strip():
                    query_embedding = json_lib.loads(raw)
                elif isinstance(raw, list) and raw and isinstance(raw[0], (int, float)):
                    pass  # already parsed as list of floats

            stored_count = 0
            store = []

            # Unwrap Embedding Node output format: {"embeddings": [...], "dimension": ...}
            if isinstance(embeddings_input, dict) and "embeddings" in embeddings_input:
                embeddings_input = embeddings_input["embeddings"]

            # Store embeddings if provided
            if embeddings_input and isinstance(embeddings_input, list):
                if chunks_input and isinstance(chunks_input, list):
                    for i, emb_item in enumerate(embeddings_input):
                        vector = self._extract_vector(emb_item)
                        if not vector:
                            continue
                        chunk_text = ""
                        chunk_id = f"{collection}-{i}"
                        if i < len(chunks_input):
                            c = chunks_input[i]
                            chunk_text = (c.get("text") or c.get("chunk_text") or "") if isinstance(c, dict) else str(c)
                            chunk_id = c.get("index", chunk_id) if isinstance(c, dict) else chunk_id
                        store.append({
                            "vector": vector,
                            "chunk_text": chunk_text,
                            "chunk_id": str(chunk_id),
                        })
                        stored_count += 1
                else:
                    for i, emb_item in enumerate(embeddings_input):
                        vector = self._extract_vector(emb_item)
                        if not vector:
                            continue
                        chunk_text = emb_item.get("chunk_text", "") if isinstance(emb_item, dict) else ""
                        store.append({
                            "vector": vector,
                            "chunk_text": chunk_text,
                            "chunk_id": f"{collection}-{i}",
                        })
                        stored_count += 1

            # Retrieve if query provided
            retrieval_results = []
            query_vec = self._extract_vector(query_embedding) if query_embedding else []

            if query_vec and store:
                scored = []
                for item in store:
                    score = self._cosine_similarity(query_vec, item["vector"])
                    scored.append({
                        "chunk_text": item["chunk_text"],
                        "chunk_id": item["chunk_id"],
                        "score": round(score, 4),
                    })
                scored.sort(key=lambda x: x["score"], reverse=True)
                retrieval_results = scored[:top_k]

            # Persist the stored entries to the shared QA index, so the
            # qa-chat node can query them in the same or a later workflow run.
            if store:
                try:
                    from backend.services.qa_index import QAIndexService

                    QAIndexService().import_entries(store, filename=filename)
                except Exception as e:
                    logger.warning(f"Failed to persist entries to QA index: {e}")

            result.succeed({
                "stored_count": {"count": stored_count, "collection": collection},
                "results": retrieval_results,
            })

        except Exception as e:
            result.fail(str(e))

        return result

    @staticmethod
    def _extract_vector(item: Any) -> list[float] | None:
        if isinstance(item, (list, tuple)) and item:
            if isinstance(item[0], (int, float)):
                return [float(x) for x in item]
            if isinstance(item[0], dict):
                return VectorStoreNode._extract_vector(item[0])
        if isinstance(item, dict):
            for key in ("vector", "embedding"):
                v = item.get(key)
                if v and isinstance(v, (list, tuple)) and v and isinstance(v[0], (int, float)):
                    return [float(x) for x in v]
            if "embeddings" in item:
                emb = item["embeddings"]
                if isinstance(emb, (list, tuple)) and emb:
                    if isinstance(emb[0], (int, float)):
                        return [float(x) for x in emb]
                    if isinstance(emb[0], dict):
                        return VectorStoreNode._extract_vector(emb[0])
                if isinstance(emb, dict):
                    return VectorStoreNode._extract_vector(emb)
        return None

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
