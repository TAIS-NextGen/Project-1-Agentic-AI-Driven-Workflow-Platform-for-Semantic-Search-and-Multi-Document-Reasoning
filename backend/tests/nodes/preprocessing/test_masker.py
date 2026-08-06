from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.preprocessing.masker import MaskerNode, pymupdf
from backend.sdk import ExecutionContext, NodeStatus


def _create_pdf(path: Path, lines: list[str]) -> Path:
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 24
    document.save(path)
    document.close()
    return path


def _context(path: Path, inputs: dict | None = None) -> ExecutionContext:
    return ExecutionContext(
        workflow_id="wf-masker",
        node_id="masker-1",
        inputs=inputs or {
            "document": {
                "filename": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "mime_type": "application/pdf",
            }
        },
    )


def test_definition_exposes_pdf_document_output():
    node = MaskerNode(node_id="masker-1", config={})
    assert node.type == "masker"
    assert {port.name for port in node.inputs} == {"document", "text"}
    assert {port.name for port in node.outputs} == {"document", "report", "metadata"}
    assert node.outputs[0].type.value == "document"


def test_sensitive_span_detection_covers_main_categories():
    text = (
        "Email john.doe@example.com, phone +33 6 12 34 56 78, "
        "CIN: AB123456, 12 rue de Paris, IBAN FR76 3000 6000 0112 3456 7890 189, "
        "IP 192.168.1.15"
    )
    enabled = {"EMAIL", "PHONE", "ID", "ADDRESS", "FINANCIAL", "IP_ADDRESS"}
    detections = MaskerNode.detect_sensitive_spans(text, enabled)
    kinds = {item.entity_type for item in detections}
    assert {"EMAIL", "PHONE", "ID", "ADDRESS", "FINANCIAL", "IP_ADDRESS"}.issubset(kinds)


@pytest.mark.asyncio
async def test_masks_pdf_and_returns_downloadable_document(tmp_path: Path, monkeypatch):
    source = _create_pdf(
        tmp_path / "customer.pdf",
        [
            "Email: john.doe@example.com",
            "Phone: +33 6 12 34 56 78",
            "CIN: AB123456",
            "Address: 12 rue de Paris",
            "IP: 192.168.1.15",
        ],
    )
    storage = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_DIR", str(storage))

    node = MaskerNode(node_id="masker-1", config={"mask_style": "black"})
    result = await node.execute(_context(source))

    assert result.status == NodeStatus.SUCCESS, result.error
    output = result.outputs["document"]
    output_path = Path(output["path"])
    assert output_path.exists()
    assert output_path.suffix == ".pdf"
    assert output["download_url"].startswith("/data/storage/masker/")
    assert result.outputs["report"]["total_masked"] >= 5
    assert result.outputs["metadata"]["secure_redaction"] is True

    with pymupdf.open(output_path) as document:
        extracted = "\n".join(page.get_text() for page in document)
    assert "john.doe@example.com" not in extracted
    assert "+33 6 12 34 56 78" not in extracted
    assert "AB123456" not in extracted
    assert "12 rue de Paris" not in extracted
    assert "192.168.1.15" not in extracted


@pytest.mark.asyncio
async def test_recovers_pdf_from_upstream_lineage_after_text_node(tmp_path: Path, monkeypatch):
    source = _create_pdf(tmp_path / "lineage.pdf", ["Contact: user@example.org"])
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    inputs = {
        "text": "Contact: user@example.org",
        "__upstream_artifacts__": [
            {
                "source_node_id": "parser-1",
                "source_node_type": "document-parser",
                "output_port": "downloads",
                "distance": 1,
                "value": {"text": {"path": str(tmp_path / "parser-output.txt")}},
            },
            {
                "source_node_id": "parser-1",
                "source_node_type": "document-parser",
                "output_port": "text",
                "distance": 1,
                "value": "Contact: user@example.org",
            },
            {
                "source_node_id": "input-1",
                "source_node_type": "document-upload",
                "output_port": "document",
                "distance": 2,
                "value": {"filename": source.name, "path": str(source)},
            },
        ],
    }
    node = MaskerNode(node_id="masker-1", config={})
    result = await node.execute(_context(source, inputs))

    assert result.status == NodeStatus.SUCCESS, result.error
    assert result.outputs["metadata"]["source_node_type"] == "document-upload"
    assert result.outputs["report"]["by_type"]["EMAIL"] == 1


@pytest.mark.asyncio
async def test_fails_for_pdf_without_searchable_text(tmp_path: Path, monkeypatch):
    source = tmp_path / "scan.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(source)
    document.close()
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))

    node = MaskerNode(node_id="masker-1", config={})
    result = await node.execute(_context(source))

    assert result.status == NodeStatus.FAILURE
    assert "no searchable text layer" in (result.error or "").lower()
