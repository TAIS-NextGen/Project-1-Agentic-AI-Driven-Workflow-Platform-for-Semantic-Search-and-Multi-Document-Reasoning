from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.extraction.handwriting_ocr import HandwritingOCRNode
from backend.sdk import ExecutionContext, NodeStatus
from backend.services.storage import StorageService


@pytest.fixture
def node():
    return HandwritingOCRNode(node_id="test-hwocr-1", config={})


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    draw.text((20, 40), "Hello World", fill="black", font=font)
    draw.text((20, 90), "Test Handwriting", fill="black", font=font)

    f = tmp_path / "handwritten.png"
    img.save(f)
    return f


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    f = tmp_path / "document.pdf"
    f.write_bytes(b"%PDF-1.4 mock pdf content")
    return f


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    f = tmp_path / "notes.txt"
    f.write_bytes(b"Hello, world!")
    return f


@pytest.fixture
def upload_dir(monkeypatch, tmp_path: Path) -> Path:
    d = tmp_path / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(d))
    return d


def test_node_definition(node: HandwritingOCRNode):
    assert node.type == "handwriting-ocr"
    assert node.name == "Handwriting OCR"
    assert node.category == "extraction"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "image"
    assert node.inputs[0].type.value == "image"
    assert len(node.outputs) == 3
    assert len(node.config_fields) == 4
    output_names = {p.name for p in node.outputs}
    assert output_names == {"text", "confidence", "details"}


@pytest.mark.asyncio
async def test_execute_with_image(node: HandwritingOCRNode, sample_image: Path):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-hwocr-1",
        inputs={
            "image": {
                "filename": sample_image.name,
                "path": str(sample_image),
                "size_bytes": sample_image.stat().st_size,
            }
        },
        config={},
        services={"storage": StorageService()},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    assert isinstance(result.outputs["text"], str)
    assert len(result.outputs["text"]) > 0
    assert result.outputs["confidence"] >= 0
    assert result.outputs["details"]["total_lines"] > 0
    assert result.outputs["details"]["filename"] == sample_image.name


@pytest.mark.asyncio
async def test_execute_with_file_id(sample_image: Path, upload_dir: Path):
    import shutil

    stored = upload_dir / sample_image.name
    shutil.copy2(sample_image, stored)

    file_id = stored.stem

    node = HandwritingOCRNode(node_id="test-hwocr-1", config={"file_id": file_id})

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-hwocr-1",
        inputs={},
        config={"file_id": file_id},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    assert isinstance(result.outputs["text"], str)


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: HandwritingOCRNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-hwocr-1",
        inputs={},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No file provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_for_disallowed_extension(tmp_path: Path):
    exe_file = tmp_path / "malware.exe"
    exe_file.write_bytes(b"fake exe")

    node = HandwritingOCRNode(
        node_id="test-hwocr-1",
        config={"allowed_extensions": [".png", ".jpg"]},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-hwocr-1",
        inputs={
            "image": {
                "filename": exe_file.name,
                "path": str(exe_file),
                "size_bytes": exe_file.stat().st_size,
            }
        },
        config={"allowed_extensions": [".png", ".jpg"]},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert ".exe" in result.error


@pytest.mark.asyncio
async def test_execute_fails_for_pdf(node: HandwritingOCRNode, sample_pdf: Path):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-hwocr-1",
        inputs={
            "image": {
                "filename": sample_pdf.name,
                "path": str(sample_pdf),
                "size_bytes": sample_pdf.stat().st_size,
            }
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert ".pdf" in result.error


@pytest.mark.asyncio
async def test_execute_fails_for_oversized_file(sample_image: Path):
    node = HandwritingOCRNode(
        node_id="test-hwocr-1",
        config={"max_file_size_mb": 1},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-hwocr-1",
        inputs={
            "image": {
                "filename": sample_image.name,
                "path": str(sample_image),
                "size_bytes": 100 * 1024 * 1024,
            }
        },
        config={"max_file_size_mb": 1},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "exceeds maximum" in result.error


@pytest.mark.asyncio
async def test_execute_fails_when_file_id_not_found(tmp_path: Path):
    node = HandwritingOCRNode(
        node_id="test-hwocr-1", config={"file_id": "does-not-exist"}
    )

    upload_dir = tmp_path / "nonexistent"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-hwocr-1",
        inputs={},
        config={"file_id": "does-not-exist"},
        services={"storage": StorageService()},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "not found" in result.error


def test_to_definition_returns_correct_shape(node: HandwritingOCRNode):
    definition = node.to_definition()
    assert definition["type"] == "handwriting-ocr"
    assert definition["name"] == "Handwriting OCR"
    assert definition["category"] == "extraction"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 3
    assert len(definition["config_fields"]) == 4
