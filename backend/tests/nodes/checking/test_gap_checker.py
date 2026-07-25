from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.nodes.checking.gap_checker import GapCheckerNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return GapCheckerNode(node_id="test-gap-1", config={})


@pytest.fixture
def sample_text_doc(tmp_path: Path) -> Path:
    f = tmp_path / "invoice.txt"
    f.write_text(
        "Facture N F2024-156\n"
        "Date: 12/06/2024\n"
        "Fournisseur: Societe ABC\n"
        "Client: Jean Dupont\n"
        "Montant TTC: 2500 DT\n"
        "TVA: 19%\n",
        encoding="utf-8",
    )
    return f


@pytest.fixture
def incomplete_text_doc(tmp_path: Path) -> Path:
    f = tmp_path / "partial.txt"
    f.write_text(
        "Date: 15/03/2024\n"
        "Just some random text\n"
        "No invoice number here\n",
        encoding="utf-8",
    )
    return f


def test_node_definition(node: GapCheckerNode):
    assert node.type == "gap-checker"
    assert node.name == "Gap Checker"
    assert node.category == "checking"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "document"
    assert len(node.outputs) == 3
    assert len(node.config_fields) == 6
    output_names = {p.name for p in node.outputs}
    assert output_names == {"report", "score", "missing"}


def test_to_definition_returns_correct_shape(node: GapCheckerNode):
    definition = node.to_definition()
    assert definition["type"] == "gap-checker"
    assert definition["name"] == "Gap Checker"
    assert definition["category"] == "checking"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 3
    assert len(definition["config_fields"]) == 6


@pytest.mark.asyncio
async def test_execute_with_text_doc(sample_text_doc: Path):
    node = GapCheckerNode(node_id="test-gap-2", config={
        "template": "invoice_fr",
        "evaluation_mode": "deterministic_only",
    })
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-gap-2",
        inputs={
            "document": {
                "filename": sample_text_doc.name,
                "path": str(sample_text_doc),
                "size_bytes": sample_text_doc.stat().st_size,
            }
        },
        config={"template": "invoice_fr", "evaluation_mode": "deterministic_only"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    score = result.outputs["score"]
    assert score["total_fields"] == 6
    assert score["matched"] > 0
    assert score["percentage"] > 0


@pytest.mark.asyncio
async def test_execute_detects_missing_fields(incomplete_text_doc: Path):
    node = GapCheckerNode(node_id="test-gap-3", config={
        "template": "invoice_fr",
        "evaluation_mode": "deterministic_only",
    })
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-gap-3",
        inputs={
            "document": {
                "filename": incomplete_text_doc.name,
                "path": str(incomplete_text_doc),
                "size_bytes": incomplete_text_doc.stat().st_size,
            }
        },
        config={"template": "invoice_fr", "evaluation_mode": "deterministic_only"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    score = result.outputs["score"]
    assert score["percentage"] < 100.0
    missing = result.outputs["missing"]
    assert len(missing) > 0


@pytest.mark.asyncio
async def test_execute_deterministic_only_mode(incomplete_text_doc: Path):
    node = GapCheckerNode(node_id="test-gap-4", config={
        "template": "generic",
        "evaluation_mode": "deterministic_only",
    })
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-gap-4",
        inputs={
            "document": {
                "filename": incomplete_text_doc.name,
                "path": str(incomplete_text_doc),
                "size_bytes": incomplete_text_doc.stat().st_size,
            }
        },
        config={"template": "generic", "evaluation_mode": "deterministic_only"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    report = result.outputs["report"]
    for field in report["fields"]:
        assert field["method"] in ("regex", "skipped")


@pytest.mark.asyncio
async def test_execute_with_custom_checklist(sample_text_doc: Path):
    custom = json.dumps([
        {
            "key": "test_reference",
            "label": "Reference",
            "required": True,
            "severity": "CRITICAL",
            "pattern": "F2024-\\d+",
        },
        {
            "key": "test_date",
            "label": "Date",
            "required": True,
            "severity": "CRITICAL",
            "pattern": "\\d{2}/\\d{2}/\\d{4}",
        },
    ])
    node = GapCheckerNode(node_id="test-gap-5", config={
        "custom_checklist": custom,
        "evaluation_mode": "deterministic_only",
    })
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-gap-5",
        inputs={
            "document": {
                "filename": sample_text_doc.name,
                "path": str(sample_text_doc),
                "size_bytes": sample_text_doc.stat().st_size,
            }
        },
        config={"custom_checklist": custom, "evaluation_mode": "deterministic_only"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    score = result.outputs["score"]
    assert score["total_fields"] == 2
    assert score["matched"] == 2
    assert score["percentage"] == 100.0


@pytest.mark.asyncio
async def test_execute_with_image_doc(tmp_path: Path):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 400), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    draw.text((50, 50), "Facture N F2024-999", fill="black", font=font)
    draw.text((50, 100), "Date: 20/08/2024", fill="black", font=font)
    draw.text((50, 150), "Montant TTC: 1500 DT", fill="black", font=font)

    img_file = tmp_path / "invoice_img.png"
    img.save(img_file)

    node = GapCheckerNode(node_id="test-gap-6", config={
        "template": "generic",
        "evaluation_mode": "deterministic_only",
    })
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-gap-6",
        inputs={
            "document": {
                "filename": img_file.name,
                "path": str(img_file),
                "size_bytes": img_file.stat().st_size,
            }
        },
        config={"template": "generic", "evaluation_mode": "deterministic_only"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    score = result.outputs["score"]
    assert score["total_fields"] > 0


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: GapCheckerNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-gap-1",
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

    node = GapCheckerNode(
        node_id="test-gap-7",
        config={"allowed_extensions": [".pdf", ".png", ".txt"], "evaluation_mode": "deterministic_only"},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-gap-7",
        inputs={
            "document": {
                "filename": exe_file.name,
                "path": str(exe_file),
                "size_bytes": exe_file.stat().st_size,
            }
        },
        config={"allowed_extensions": [".pdf", ".png", ".txt"], "evaluation_mode": "deterministic_only"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert ".exe" in result.error
