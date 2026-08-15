from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.normalization.text_cleaner import TextCleanerNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return TextCleanerNode(node_id="test-cleaner-1", config={})


@pytest.fixture
def upload_dir(monkeypatch, tmp_path: Path) -> Path:
    d = tmp_path / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(d))
    return d


def test_node_definition(node: TextCleanerNode):
    assert node.type == "text-cleaner"
    assert node.name == "Text Cleaner"
    assert node.category == "normalization"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "text"
    assert len(node.outputs) == 3
    output_names = {p.name for p in node.outputs}
    assert output_names == {"cleaned_text", "stats", "dates"}
    assert len(node.config_fields) == 7


@pytest.mark.asyncio
async def test_execute_basic_cleaning():
    node = TextCleanerNode(node_id="test-cleaner-1", config={})

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-cleaner-1",
        inputs={"text": "Hello    world.\nThis is a docu-\nment  with   spaces."},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["cleaned_text"] == "Hello world.\nThis is a document with spaces."
    assert result.outputs["stats"]["chars_removed"] > 0


@pytest.mark.asyncio
async def test_execute_with_casing():
    node = TextCleanerNode(node_id="test-cleaner-1", config={"normalize_casing": "upper"})

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-cleaner-1",
        inputs={"text": "Hello World"},
        config={"normalize_casing": "upper"},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["cleaned_text"] == "HELLO WORLD"


@pytest.mark.asyncio
async def test_execute_with_date_normalization():
    node = TextCleanerNode(node_id="test-cleaner-1", config={"normalize_dates": True})

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-cleaner-1",
        inputs={"text": "Invoice date: 15/03/2024"},
        config={"normalize_dates": True},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert len(result.outputs["dates"]) > 0
    assert result.outputs["stats"]["dates_normalized"] > 0

@pytest.mark.asyncio
async def test_execute_with_file_id(upload_dir: Path):
    file_id = "sample-text"
    stored = upload_dir / f"{file_id}.txt"
    stored.write_text("Raw   text    from a file.", encoding="utf-8")

    node = TextCleanerNode(node_id="test-cleaner-1", config={"file_id": file_id})

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-cleaner-1",
        inputs={},
        config={"file_id": file_id},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["cleaned_text"] == "Raw text from a file."


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: TextCleanerNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-cleaner-1",
        inputs={},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No text provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_when_file_id_not_found(tmp_path: Path):
    node = TextCleanerNode(node_id="test-cleaner-1", config={"file_id": "does-not-exist"})

    upload_dir = tmp_path / "nonexistent"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-cleaner-1",
        inputs={},
        config={"file_id": "does-not-exist"},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No readable text found" in result.error


def test_to_definition_returns_correct_shape(node: TextCleanerNode):
    definition = node.to_definition()
    assert definition["type"] == "text-cleaner"
    assert definition["name"] == "Text Cleaner"
    assert definition["category"] == "normalization"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 3
    assert len(definition["config_fields"]) == 7