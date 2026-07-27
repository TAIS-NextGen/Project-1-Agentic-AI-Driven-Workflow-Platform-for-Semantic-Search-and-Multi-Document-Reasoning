from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.extraction.table_extractor import TableExtractorNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return TableExtractorNode(node_id="test-table-1", config={})


@pytest.fixture
def sample_table_image(tmp_path: Path) -> Path:
    from PIL import Image, ImageDraw

    f = tmp_path / "table_sample.png"
    img = Image.new("RGB", (400, 300), color="white")
    draw = ImageDraw.Draw(img)

    # Draw a simple 3x3 grid to simulate a table
    for x in range(50, 350, 100):
        draw.line([(x, 50), (x, 250)], fill="black", width=2)
    for y in range(50, 250, 66):
        draw.line([(50, y), (350, y)], fill="black", width=2)

    img.save(f)
    return f


@pytest.fixture
def sample_plain_image(tmp_path: Path) -> Path:
    from PIL import Image

    f = tmp_path / "plain.png"
    img = Image.new("RGB", (200, 200), color="white")
    img.save(f)
    return f


@pytest.fixture
def upload_dir(monkeypatch, tmp_path: Path) -> Path:
    d = tmp_path / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(d))
    return d


def test_node_definition(node: TableExtractorNode):
    assert node.type == "table-extractor"
    assert node.name == "Table Extractor"
    assert node.category == "extraction"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "document"
    assert len(node.outputs) == 2
    output_names = {p.name for p in node.outputs}
    assert output_names == {"tables", "table_count"}
    assert len(node.config_fields) == 2


@pytest.mark.asyncio
async def test_execute_with_no_tables(node: TableExtractorNode, sample_plain_image: Path):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-table-1",
        inputs={
            "document": {
                "filename": sample_plain_image.name,
                "path": str(sample_plain_image),
                "size_bytes": sample_plain_image.stat().st_size,
            }
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert isinstance(result.outputs["tables"], list)
    assert result.outputs["table_count"] == len(result.outputs["tables"])


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: TableExtractorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-table-1",
        inputs={},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No document provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_when_file_id_not_found(tmp_path: Path):
    node = TableExtractorNode(node_id="test-table-1", config={"file_id": "does-not-exist"})

    upload_dir = tmp_path / "nonexistent"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-table-1",
        inputs={},
        config={"file_id": "does-not-exist"},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "not found" in result.error


def test_to_definition_returns_correct_shape(node: TableExtractorNode):
    definition = node.to_definition()
    assert definition["type"] == "table-extractor"
    assert definition["name"] == "Table Extractor"
    assert definition["category"] == "extraction"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 2
    assert len(definition["config_fields"]) == 2