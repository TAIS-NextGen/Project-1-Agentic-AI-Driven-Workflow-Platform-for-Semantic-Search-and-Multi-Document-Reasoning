from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.ingestion.watermark_remover import WatermarkRemoverNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return WatermarkRemoverNode(node_id="test-watermark-1", config={})


@pytest.fixture
def watermarked_image(tmp_path: Path) -> Path:
    from PIL import Image, ImageDraw

    f = tmp_path / "watermarked.png"
    img = Image.new("RGB", (200, 200), color=(40, 40, 40))
    draw = ImageDraw.Draw(img)
    # Light block simulates a semi-transparent watermark overlay
    draw.rectangle([50, 50, 150, 150], fill=(230, 230, 230))
    img.save(f)
    return f


@pytest.fixture
def plain_pdf(tmp_path: Path) -> Path:
    import fitz

    f = tmp_path / "plain.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((50, 50), "Sample content, no watermark layer")
    doc.save(str(f))
    doc.close()
    return f


@pytest.fixture
def pdf_with_ocg_watermark(tmp_path: Path) -> Path:
    import fitz

    f = tmp_path / "ocg_watermark.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((50, 50), "Real content")

    ocg_xref = doc.add_ocg("Watermark", on=True)
    page.insert_textbox((50, 200, 250, 250), "CONFIDENTIAL", oc=ocg_xref)

    doc.save(str(f))
    doc.close()
    return f


@pytest.fixture
def upload_dir(monkeypatch, tmp_path: Path) -> Path:
    d = tmp_path / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(d))
    return d


def test_node_definition(node: WatermarkRemoverNode):
    assert node.type == "watermark-remover"
    assert node.name == "Watermark Remover"
    assert node.category == "ingestion"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "document"
    assert len(node.outputs) == 1
    assert node.outputs[0].name == "cleaned_document"
    assert len(node.config_fields) == 1


@pytest.mark.asyncio
async def test_execute_image_watermark_removal(
    node: WatermarkRemoverNode, watermarked_image: Path, upload_dir: Path
):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-watermark-1",
        inputs={
            "document": {
                "filename": watermarked_image.name,
                "path": str(watermarked_image),
                "size_bytes": watermarked_image.stat().st_size,
            }
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    output_path = Path(result.outputs["cleaned_document"])
    assert output_path.exists()
    assert output_path.suffix == ".png"


@pytest.mark.asyncio
async def test_execute_pdf_without_ocg_falls_back_to_rasterized(
    node: WatermarkRemoverNode, plain_pdf: Path, upload_dir: Path
):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-watermark-1",
        inputs={
            "document": {
                "filename": plain_pdf.name,
                "path": str(plain_pdf),
                "size_bytes": plain_pdf.stat().st_size,
            }
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    output_path = Path(result.outputs["cleaned_document"])
    assert output_path.exists()
    assert output_path.suffix == ".pdf"


@pytest.mark.asyncio
async def test_execute_pdf_with_ocg_watermark_strips_layer(
    node: WatermarkRemoverNode, pdf_with_ocg_watermark: Path, upload_dir: Path
):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-watermark-1",
        inputs={
            "document": {
                "filename": pdf_with_ocg_watermark.name,
                "path": str(pdf_with_ocg_watermark),
                "size_bytes": pdf_with_ocg_watermark.stat().st_size,
            }
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    output_path = Path(result.outputs["cleaned_document"])
    assert output_path.exists()
    assert output_path.suffix == ".pdf"


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: WatermarkRemoverNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-watermark-1",
        inputs={},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No document provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_on_unsupported_extension(
    node: WatermarkRemoverNode, tmp_path: Path, upload_dir: Path
):
    f = tmp_path / "notes.txt"
    f.write_text("not an image or pdf")

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-watermark-1",
        inputs={
            "document": {
                "filename": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
            }
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE


def test_to_definition_returns_correct_shape(node: WatermarkRemoverNode):
    definition = node.to_definition()
    assert definition["type"] == "watermark-remover"
    assert definition["name"] == "Watermark Remover"
    assert definition["category"] == "ingestion"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 1
    assert len(definition["config_fields"]) == 1