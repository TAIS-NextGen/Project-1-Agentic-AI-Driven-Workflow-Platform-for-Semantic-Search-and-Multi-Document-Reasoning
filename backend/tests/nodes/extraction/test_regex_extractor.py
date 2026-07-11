from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.nodes.extraction.regex_extractor import RegexExtractorNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return RegexExtractorNode(node_id="test-regex-1", config={})


def test_node_definition(node: RegexExtractorNode):
    assert node.type == "regex-extractor"
    assert node.name == "Regex Extractor"
    assert node.category == "extraction"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "text"
    assert len(node.outputs) == 3
    assert len(node.config_fields) == 4
    output_names = {p.name for p in node.outputs}
    assert output_names == {"extracted", "missing", "stats"}


@pytest.mark.asyncio
async def test_extract_phone(node: RegexExtractorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-regex-1",
        inputs={"text": "Contact: Mazen, Tel: +216 21 123 456, Email: mazen@test.com"},
        config={"template": "generic", "language": "fr"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    extracted = result.outputs["extracted"]
    contact = extracted.get("contact", {})
    assert contact.get("phone", {}).get("value") == "+216 21 123 456"
    assert contact.get("phone", {}).get("confidence", 0) > 0


@pytest.mark.asyncio
async def test_extract_date_and_amount(node: RegexExtractorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-regex-1",
        inputs={"text": "Facture N123 | Date: 15/03/2024 | Montant TTC: 1500 DT"},
        config={"template": "generic", "language": "fr"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    extracted = result.outputs["extracted"]
    dates = extracted.get("dates", {})
    financial = extracted.get("financial", {})
    assert "15/03/2024" in str(dates) or dates.get("date", {}).get("value") == "15/03/2024"
    assert "1500" in str(financial) or "1500" in str(financial.get("amount", ""))


@pytest.mark.asyncio
async def test_extract_with_template_invoice_fr():
    node = RegexExtractorNode(node_id="test-regex-3", config={"template": "invoice_fr", "language": "fr"})
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-regex-3",
        inputs={"text": "N° F2024-156\nDate: 12/06/2024\nFournisseur: Société ABC\nMontant TTC: 2500 DT\nTVA: 19%"},
        config={"template": "invoice_fr", "language": "fr"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    extracted = result.outputs["extracted"]
    assert any("F2024" in str(cat) for cat in extracted.values()), f"No invoice field found in {extracted}"


@pytest.mark.asyncio
async def test_extract_with_template_invoice_ar(node: RegexExtractorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-regex-1",
        inputs={"text": "رقم الفاتورة: 12345\nالتاريخ: 15/03/2024\nالمبلغ: 500 DT"},
        config={"template": "invoice_ar", "language": "ar"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    extracted = result.outputs["extracted"]
    assert any("500" in str(cat) for cat in extracted.values())


@pytest.mark.asyncio
async def test_extract_reports_missing_fields():
    node = RegexExtractorNode(node_id="test-regex-4", config={"template": "invoice_fr", "language": "fr"})
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-regex-4",
        inputs={"text": "Just some random text without any invoice data"},
        config={"template": "invoice_fr", "language": "fr"},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    missing = result.outputs["missing"]
    assert "numero_facture" in missing
    assert "date" in missing
    assert "montant" in missing


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: RegexExtractorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-regex-1",
        inputs={},
        config={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No text provided" in result.error


@pytest.mark.asyncio
async def test_execute_with_custom_patterns():
    custom_patterns = json.dumps([
        {
            "name": "code",
            "pattern": "Code:\\s*(\\w+-\\w+-\\w+)",
            "group": 1,
            "mode": "first",
            "category": "general",
            "required": False,
        },
    ])
    node = RegexExtractorNode(
        node_id="test-regex-5",
        config={"template": "custom", "custom_patterns": custom_patterns},
    )
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-regex-5",
        inputs={"text": "Code: ABC-123-XYZ\nReference: REF-456"},
        config={"template": "custom", "custom_patterns": custom_patterns},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    extracted = result.outputs["extracted"]
    assert any("ABC-123-XYZ" in str(cat) for cat in extracted.values()), f"ABC-123-XYZ not found in {extracted}"


@pytest.mark.asyncio
async def test_execute_with_file_id(node: RegexExtractorNode, tmp_path: Path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))

    txt_file = upload_dir / "test-file.txt"
    txt_file.write_text("Client: Jean Dupont\nMontant: 3000 DT", encoding="utf-8")
    file_id = txt_file.stem

    node_with_config = RegexExtractorNode(
        node_id="test-regex-2",
        config={"file_id": file_id, "template": "invoice_fr"},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-regex-2",
        inputs={},
        config={"file_id": file_id, "template": "invoice_fr"},
    )

    result = await node_with_config.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert "3000" in str(result.outputs["extracted"])


def test_to_definition_shape(node: RegexExtractorNode):
    definition = node.to_definition()
    assert definition["type"] == "regex-extractor"
    assert definition["name"] == "Regex Extractor"
    assert definition["category"] == "extraction"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 3
    assert len(definition["config_fields"]) == 4
