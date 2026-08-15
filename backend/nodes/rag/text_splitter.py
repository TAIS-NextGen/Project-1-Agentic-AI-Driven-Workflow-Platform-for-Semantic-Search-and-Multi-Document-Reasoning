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


class TextSplitterNode(BaseNode):
    type = "text-splitter"
    name = "Text Splitter"
    category = "rag"
    icon = "\u2702\ufe0f"
    color = "#a855f7"
    description = "Split text into overlapping chunks for embedding and retrieval"
    version = "1.0.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Raw or cleaned text to split into chunks",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="chunks",
            type=PortType.JSON,
            label="Chunks",
            description="Array of text chunks with index, start, and end character positions",
        ),
        Port(
            name="stats",
            type=PortType.JSON,
            label="Statistics",
            description="Chunk count, average size, and overlap details",
        ),
    ]

    config_fields = [
        ConfigField(
            key="chunk_size",
            label="Chunk Size",
            type="number",
            required=False,
            default=512,
            description="Maximum number of characters per chunk",
        ),
        ConfigField(
            key="chunk_overlap",
            label="Chunk Overlap",
            type="number",
            required=False,
            default=100,
            description="Number of overlapping characters between consecutive chunks",
        ),
        ConfigField(
            key="text",
            label="Text",
            type="text",
            required=False,
            default="",
            description="Text to split. Leave empty if provided via upstream connection.",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            chunk_size = int(config.get("chunk_size", 512))
            chunk_overlap = int(config.get("chunk_overlap", 100))

            text = ctx.get_input("text", "") or str(config.get("text", ""))
            if not isinstance(text, str) or not text.strip():
                result.fail("No text provided via input port or 'text' config field")
                return result

            if chunk_overlap >= chunk_size:
                result.fail(f"Chunk overlap ({chunk_overlap}) must be less than chunk size ({chunk_size})")
                return result

            chunks = self._split_text(text, chunk_size, chunk_overlap)

            avg_size = round(sum(len(c["text"]) for c in chunks) / max(len(chunks), 1), 1)

            result.succeed({
                "chunks": chunks,
                "stats": {
                    "total_chunks": len(chunks),
                    "avg_chunk_size": avg_size,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                    "total_chars": len(text),
                },
            })

        except Exception as e:
            result.fail(str(e))

        return result

    @staticmethod
    def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        start = 0
        index = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]

            chunks.append({
                "index": index,
                "text": chunk_text,
                "char_start": start,
                "char_end": end,
            })

            index += 1
            if end >= len(text):
                break
            start = end - chunk_overlap

        return chunks
