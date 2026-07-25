from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.structure.structure_analyzer import DocumentStructureAnalyzerNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return DocumentStructureAnalyzerNode(node_id="test-struct-1", config={})


@pytest.fixture
def sample_image_doc(tmp_path: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("arial.ttf", 32)
        body_font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    draw.text((50, 30), "Rapport Annuel 2024", fill="black", font=title_font)
    draw.text((50, 100), "Ce rapport presente les resultats financiers de l entreprise.", fill="black", font=body_font)
    draw.text((50, 150), "Le chiffre d affaires a augmente de 15%.", fill="black", font=body_font)
    draw.text((50, 220), "Les perspectives pour 2025 sont encourageantes.", fill="black", font=body_font)

    f = tmp_path / "report.png"
    img.save(f)
    return f


@pytest.fixture
def sample_pdf_doc(tmp_path: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("arial.ttf", 32)
        body_font = ImageFont.truetype("arial.ttf", 18)
        small_font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.text((50, 20), "Rapport Confidentiel", fill="black", font=small_font)
    draw.text((50, 60), "Rapport Annuel 2024", fill="black", font=title_font)
    draw.text((50, 130), "1. Introduction", fill="black", font=body_font)
    draw.text((50, 170), "Ce rapport couvre la periode du 1er janvier au 31 decembre 2024.", fill="black", font=body_font)
    draw.text((50, 210), "2. Resultats Financiers", fill="black", font=body_font)
    draw.text((50, 250), "Le chiffre d affaires total est de 2 500 000 DT.", fill="black", font=body_font)
    draw.text((50, 310), "3. Conclusion", fill="black", font=body_font)
    draw.text((50, 350), "L entreprise maintient une croissance stable.", fill="black", font=body_font)
    draw.text((50, 580), "Page 1/1 - CONFIDENTIEL", fill="black", font=small_font)

    f = tmp_path / "report.pdf"
    img.save(f, "PDF")
    return f


@pytest.fixture
def upload_dir(monkeypatch, tmp_path: Path) -> Path:
    d = tmp_path / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(d))
    return d


def test_node_definition(node: DocumentStructureAnalyzerNode):
    assert node.type == "document-structure-analyzer"
    assert node.name == "Document Structure Analyzer"
    assert node.category == "structure"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "document"
    assert len(node.outputs) == 2
    assert len(node.config_fields) == 4
    output_names = {p.name for p in node.outputs}
    assert output_names == {"structure", "summary"}


@pytest.mark.asyncio
async def test_execute_with_image(node: DocumentStructureAnalyzerNode, sample_image_doc: Path):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-struct-1",
        inputs={
            "document": {
                "filename": sample_image_doc.name,
                "path": str(sample_image_doc),
                "size_bytes": sample_image_doc.stat().st_size,
            }
        },
        config={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    structure = result.outputs["structure"]
    assert len(structure) > 0
    assert len(structure[0]["layout"]) > 0
    assert "total_pages" in result.outputs["summary"]


@pytest.mark.asyncio
async def test_execute_with_pdf(node: DocumentStructureAnalyzerNode, sample_pdf_doc: Path):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-struct-1",
        inputs={
            "document": {
                "filename": sample_pdf_doc.name,
                "path": str(sample_pdf_doc),
                "size_bytes": sample_pdf_doc.stat().st_size,
            }
        },
        config={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    structure = result.outputs["structure"]
    assert len(structure) > 0
    layout_regions = structure[0]["layout"]
    assert len(layout_regions) > 0
    layout_types = {r["type"] for r in layout_regions}
    assert len(layout_types) > 0


@pytest.mark.asyncio
async def test_execute_with_file_id(sample_image_doc: Path, upload_dir: Path):
    import shutil

    stored = upload_dir / sample_image_doc.name
    shutil.copy2(sample_image_doc, stored)

    file_id = stored.stem

    node = DocumentStructureAnalyzerNode(
        node_id="test-struct-2",
        config={"file_id": file_id},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-struct-2",
        inputs={},
        config={"file_id": file_id},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    structure = result.outputs["structure"]
    assert len(structure) > 0


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: DocumentStructureAnalyzerNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-struct-1",
        inputs={},
        config={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No file provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_for_disallowed_extension(tmp_path: Path):
    exe_file = tmp_path / "malware.exe"
    exe_file.write_bytes(b"fake exe")

    node = DocumentStructureAnalyzerNode(
        node_id="test-struct-3",
        config={"allowed_extensions": [".pdf", ".png"]},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-struct-3",
        inputs={
            "document": {
                "filename": exe_file.name,
                "path": str(exe_file),
                "size_bytes": exe_file.stat().st_size,
            }
        },
        config={"allowed_extensions": [".pdf", ".png"]},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert ".exe" in result.error


@pytest.mark.asyncio
async def test_execute_fails_for_oversized_file(sample_image_doc: Path):
    node = DocumentStructureAnalyzerNode(
        node_id="test-struct-4",
        config={"max_file_size_mb": 1},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-struct-4",
        inputs={
            "document": {
                "filename": sample_image_doc.name,
                "path": str(sample_image_doc),
                "size_bytes": 100 * 1024 * 1024,
            }
        },
        config={"max_file_size_mb": 1},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "exceeds maximum" in result.error


@pytest.mark.asyncio
async def test_execute_fails_when_file_id_not_found(tmp_path: Path):
    node = DocumentStructureAnalyzerNode(
        node_id="test-struct-5",
        config={"file_id": "does-not-exist"},
    )

    upload_dir = tmp_path / "nonexistent"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-struct-5",
        inputs={},
        config={"file_id": "does-not-exist"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "not found" in result.error


def test_to_definition_returns_correct_shape(node: DocumentStructureAnalyzerNode):
    definition = node.to_definition()
    assert definition["type"] == "document-structure-analyzer"
    assert definition["name"] == "Document Structure Analyzer"
    assert definition["category"] == "structure"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 2
    assert len(definition["config_fields"]) == 4
