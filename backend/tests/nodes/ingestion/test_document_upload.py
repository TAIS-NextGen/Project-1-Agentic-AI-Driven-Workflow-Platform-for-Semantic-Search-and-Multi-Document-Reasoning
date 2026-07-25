from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.ingestion.document_upload import DocumentUploadNode
from backend.sdk import ExecutionContext, NodeStatus
from backend.services.storage import StorageService


@pytest.fixture
def node():
    return DocumentUploadNode(node_id="test-upload-1", config={})


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    f = tmp_path / "test.pdf"
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


def test_node_definition(node: DocumentUploadNode):
    assert node.type == "document-upload"
    assert node.name == "Document Upload"
    assert node.category == "ingestion"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "file"
    assert len(node.outputs) == 5
    assert len(node.config_fields) == 3
    output_names = {p.name for p in node.outputs}
    assert output_names == {"document", "file_path", "file_name", "mime_type", "size_bytes"}


@pytest.mark.asyncio
async def test_execute_with_file_input(node: DocumentUploadNode, sample_pdf: Path):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-upload-1",
        inputs={
            "file": {
                "filename": sample_pdf.name,
                "path": str(sample_pdf),
                "size_bytes": sample_pdf.stat().st_size,
            }
        },
        config={},
        services={"storage": StorageService()},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["file_name"] == "test.pdf"
    assert result.outputs["size_bytes"] == sample_pdf.stat().st_size
    assert result.outputs["mime_type"] == "application/pdf"
    assert result.outputs["file_path"] is not None
    assert Path(result.outputs["file_path"]).exists()

    doc = result.outputs["document"]
    assert doc["filename"] == "test.pdf"
    assert doc["mime_type"] == "application/pdf"
    assert doc["size_bytes"] == sample_pdf.stat().st_size
    assert doc["extension"] == ".pdf"
    assert "id" in doc


@pytest.mark.asyncio
async def test_execute_with_file_id(sample_pdf: Path, upload_dir: Path):
    import shutil
    stored = upload_dir / sample_pdf.name
    shutil.copy2(sample_pdf, stored)

    file_id = stored.stem

    node = DocumentUploadNode(node_id="test-upload-1", config={"file_id": file_id})

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-upload-1",
        inputs={},
        config={"file_id": file_id},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["file_name"] == sample_pdf.name


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: DocumentUploadNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-upload-1",
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

    node = DocumentUploadNode(
        node_id="test-upload-1",
        config={"allowed_extensions": [".pdf", ".txt"]},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-upload-1",
        inputs={
            "file": {
                "filename": exe_file.name,
                "path": str(exe_file),
                "size_bytes": exe_file.stat().st_size,
            }
        },
        config={"allowed_extensions": [".pdf", ".txt"]},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert ".exe" in result.error


@pytest.mark.asyncio
async def test_execute_fails_for_oversized_file(sample_pdf: Path):
    node = DocumentUploadNode(
        node_id="test-upload-1",
        config={"max_file_size_mb": 1},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-upload-1",
        inputs={
            "file": {
                "filename": sample_pdf.name,
                "path": str(sample_pdf),
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
    node = DocumentUploadNode(node_id="test-upload-1", config={"file_id": "does-not-exist"})

    upload_dir = tmp_path / "nonexistent"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-upload-1",
        inputs={},
        config={"file_id": "does-not-exist"},
        services={"storage": StorageService()},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "not found" in result.error


def test_to_definition_returns_correct_shape(node: DocumentUploadNode):
    definition = node.to_definition()
    assert definition["type"] == "document-upload"
    assert definition["name"] == "Document Upload"
    assert definition["category"] == "ingestion"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 5
    assert len(definition["config_fields"]) == 3
