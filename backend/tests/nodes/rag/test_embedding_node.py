from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.nodes.rag.embedding_node import EmbeddingNode
from backend.sdk import ExecutionContext, NodeStatus
from backend.services.embedding import EmbeddingService


@pytest.fixture
def node():
    return EmbeddingNode(node_id="test-embedding-1", config={})


@pytest.fixture
def mock_embed(monkeypatch):
    async def _fake_embed(self, chunks: list[str]):
        return {
            "embeddings": [{"chunk": c, "vector": [0.1, 0.2, 0.3]} for c in chunks],
            "dimension": 3,
            "model": self.model_name,
        }

    monkeypatch.setattr(EmbeddingService, "embed", _fake_embed)


def test_node_definition(node: EmbeddingNode):
    assert node.type == "embedding-node"
    assert node.name == "Embedding Node"
    assert node.category == "rag"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "chunks"
    assert len(node.outputs) == 2
    output_names = {p.name for p in node.outputs}
    assert output_names == {"embeddings", "dimension"}
    assert len(node.config_fields) == 1


@pytest.mark.asyncio
async def test_execute_success(node: EmbeddingNode, mock_embed):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-embedding-1",
        inputs={"chunks": ["First chunk of text.", "Second chunk of text."]},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["dimension"] == 3
    assert len(result.outputs["embeddings"]) == 2
    assert result.outputs["embeddings"][0]["chunk"] == "First chunk of text."
    assert result.outputs["embeddings"][0]["vector"] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_execute_uses_configured_model(monkeypatch):
    captured = {}

    async def _fake_embed(self, chunks: list[str]):
        captured["model_name"] = self.model_name
        return {
            "embeddings": [{"chunk": c, "vector": [0.0]} for c in chunks],
            "dimension": 1,
            "model": self.model_name,
        }

    monkeypatch.setattr(EmbeddingService, "embed", _fake_embed)

    node = EmbeddingNode(
        node_id="test-embedding-1",
        config={"model_name": "intfloat/e5-small-v2"},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-embedding-1",
        inputs={"chunks": ["Some text."]},
        config={"model_name": "intfloat/e5-small-v2"},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert captured["model_name"] == "intfloat/e5-small-v2"

@pytest.mark.asyncio
async def test_execute_fails_with_no_chunks(node: EmbeddingNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-embedding-1",
        inputs={},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No chunks provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_with_empty_list(node: EmbeddingNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-embedding-1",
        inputs={"chunks": []},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No chunks provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_when_chunks_not_a_list(node: EmbeddingNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-embedding-1",
        inputs={"chunks": "not a list"},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No chunks provided" in result.error


@pytest.mark.asyncio
async def test_execute_filters_invalid_chunks(node: EmbeddingNode, mock_embed):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-embedding-1",
        inputs={"chunks": ["Valid chunk.", "", "   ", None, 42, "Another valid one."]},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    embedded_chunks = [e["chunk"] for e in result.outputs["embeddings"]]
    assert embedded_chunks == ["Valid chunk.", "Another valid one."]


@pytest.mark.asyncio
async def test_execute_fails_when_all_chunks_invalid(node: EmbeddingNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-embedding-1",
        inputs={"chunks": ["", "   ", None, 42]},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "no valid non-empty strings" in result.error


def test_to_definition_returns_correct_shape(node: EmbeddingNode):
    definition = node.to_definition()
    assert definition["type"] == "embedding-node"
    assert definition["name"] == "Embedding Node"
    assert definition["category"] == "rag"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 2
    assert len(definition["config_fields"]) == 1