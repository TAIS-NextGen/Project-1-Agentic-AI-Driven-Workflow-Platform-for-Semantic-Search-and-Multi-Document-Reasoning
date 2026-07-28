from __future__ import annotations

from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)
from backend.services.embedding import EmbeddingService


class EmbeddingNode(BaseNode):
    type = "embedding-node"
    name = "Embedding Node"
    category = "rag"
    icon = "🔢"
    color = "#a855f7"
    description = "Convert text chunks into vector embeddings using a local model"
    version = "1.0.0"

    inputs = [
        Port(
            name="chunks",
            type=PortType.JSON,
            label="Chunks",
            description="List of text chunks to embed (from Text Chunker)",
            required=True,
        ),
    ]

    outputs = [
        Port(
            name="embeddings",
            type=PortType.JSON,
            label="Embeddings",
            description="List of {chunk, vector} pairs",
        ),
        Port(
            name="dimension",
            type=PortType.JSON,
            label="Vector Dimension",
            description="Length of each embedding vector",
        ),
    ]

    config_fields = [
        ConfigField(
            key="model_name",
            label="Model",
            type="text",
            required=False,
            default="BAAI/bge-small-en-v1.5",
            description="Sentence-transformers model name (bge or e5 family recommended)",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            model_name = config.get("model_name", "BAAI/bge-small-en-v1.5")

            chunks: list[str] | None = ctx.get_input("chunks")
            if not chunks or not isinstance(chunks, list):
                result.fail("No chunks provided via input port")
                return result

            valid_chunks = [c for c in chunks if isinstance(c, str) and c.strip()]
            if not valid_chunks:
                result.fail("Chunks input contained no valid non-empty strings")
                return result

            service = EmbeddingService(model_name=model_name)
            embedding_result = await service.embed(valid_chunks)

            result.succeed({
                "embeddings": embedding_result["embeddings"],
                "dimension": embedding_result["dimension"],
            })

        except Exception as e:
            result.fail(str(e))

        return result