from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.extraction.ocr_node import OCRNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return OCRNode(node_id="test-ocr-1", config={})


@pytest.fixture
def sample_text_image(tmp_path: Path) -> Path:
    from PIL import Image, ImageDraw

    f = tmp_path / "text_sample.png"
    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 40), "Hello World", fill="black")
    img.save(f)
    return f


@pytest.fixture
def upload_dir(monkeypatch, tmp_path: Path) -> Path:
    d = tmp_path / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(d))
    return d


def test_node_definition(node: OCRNode):
    assert node.type == "ocr-node"
    assert node.name == "OCR Node"
    assert node.category == "extraction"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "document"
    assert len(node.outputs) == 3
    output_names = {p.name for p in node.outputs}
    assert output_names == {"text", "lines", "stats"}
    assert len(node.config_fields) == 3


@pytest.mark.asyncio
async def test_execute_image_ocr(node: OCRNode, sample_text_image: Path):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-ocr-1",
        inputs={
            "document": {
                "filename": sample_text_image.name,
                "path": str(sample_text_image),
                "size_bytes": sample_text_image.stat().st_size,
            }
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    normalized = result.outputs["text"].replace(" ", "").lower()
    assert "hello" in normalized
    assert "world" in normalized
    assert result.outputs["stats"]["total_lines"] > 0


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: OCRNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-ocr-1",
        inputs={},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No document provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_when_file_id_not_found(tmp_path: Path):
    node = OCRNode(node_id="test-ocr-1", config={"file_id": "does-not-exist"})

    upload_dir = tmp_path / "nonexistent"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-ocr-1",
        inputs={},
        config={"file_id": "does-not-exist"},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "not found" in result.error


def test_to_definition_returns_correct_shape(node: OCRNode):
    definition = node.to_definition()
    assert definition["type"] == "ocr-node"
    assert definition["name"] == "OCR Node"
    assert definition["category"] == "extraction"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 3
    assert len(definition["config_fields"]) == 3