from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.agents.comparison_agent import ComparisonAgentNode
from backend.sdk import ExecutionContext, NodeStatus


def _document(path: Path) -> dict:
    return {
        "filename": path.name,
        "path": str(path),
        "file_path": str(path),
        "size_bytes": path.stat().st_size,
    }


def test_definition_exposes_two_required_document_inputs():
    node = ComparisonAgentNode("compare", {})
    assert node.type == "comparison-agent"
    assert [port.name for port in node.inputs] == ["original_document", "revised_document"]
    assert all(port.required for port in node.inputs)
    assert {port.name for port in node.outputs} == {"comparison", "summary", "diff", "downloads", "metadata"}


@pytest.mark.asyncio
async def test_compares_two_documents_and_reports_added_removed_modified(tmp_path: Path):
    original = tmp_path / "contract-v1.txt"
    original.write_text(
        "Contract title\nClient: Acme\nDuration: 12 months\nPrice: 1000 EUR\nEnd of document\n",
        encoding="utf-8",
    )
    revised = tmp_path / "contract-v2.txt"
    revised.write_text(
        "Contract title\nClient: Acme Corporation\nDuration: 24 months\nPayment: monthly\nEnd of document\n",
        encoding="utf-8",
    )

    node = ComparisonAgentNode("compare", {
        "comparison_level": "line",
        "ignore_whitespace": True,
        "ignore_case": False,
        "create_downloads": False,
    })
    result = await node.execute(ExecutionContext(
        "workflow",
        "compare",
        inputs={
            "original_document": _document(original),
            "revised_document": _document(revised),
        },
    ))

    assert result.status == NodeStatus.SUCCESS, result.error
    summary = result.outputs["summary"]
    assert summary["identical"] is False
    assert summary["similarity_percent"] < 100
    assert summary["change_block_count"] >= 1
    changes = result.outputs["comparison"]["changes"]
    assert any(change["type"] == "modified" for change in changes)
    assert "Client: Acme Corporation" in result.outputs["diff"]
    assert "Price: 1000 EUR" in result.outputs["diff"]


@pytest.mark.asyncio
async def test_ignore_spacing_and_case_can_mark_documents_identical(tmp_path: Path):
    original = tmp_path / "one.txt"
    original.write_text("HELLO    WORLD\n", encoding="utf-8")
    revised = tmp_path / "two.txt"
    revised.write_text("hello world\n", encoding="utf-8")

    node = ComparisonAgentNode("compare", {
        "ignore_whitespace": True,
        "ignore_case": True,
        "create_downloads": False,
    })
    result = await node.execute(ExecutionContext(
        "workflow",
        "compare",
        inputs={
            "original_document": _document(original),
            "revised_document": _document(revised),
        },
    ))

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["summary"]["identical"] is True
    assert result.outputs["summary"]["similarity_percent"] == 100.0


@pytest.mark.asyncio
async def test_creates_json_diff_html_and_zip_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    original = tmp_path / "policy-old.txt"
    original.write_text("Rule A\nRule B\n", encoding="utf-8")
    revised = tmp_path / "policy-new.txt"
    revised.write_text("Rule A\nRule C\n", encoding="utf-8")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))

    node = ComparisonAgentNode("compare", {"create_downloads": True})
    result = await node.execute(ExecutionContext(
        "workflow",
        "compare",
        inputs={
            "original_document": _document(original),
            "revised_document": _document(revised),
        },
    ))

    assert result.status == NodeStatus.SUCCESS, result.error
    downloads = result.outputs["downloads"]
    assert set(downloads) == {"json", "diff", "html", "bundle"}
    for descriptor in downloads.values():
        assert Path(descriptor["path"]).exists()
        assert descriptor["download_url"].startswith("/data/storage/comparison_outputs/")


@pytest.mark.asyncio
async def test_requires_two_documents(tmp_path: Path):
    original = tmp_path / "only.txt"
    original.write_text("One document", encoding="utf-8")
    node = ComparisonAgentNode("compare", {})
    result = await node.execute(ExecutionContext(
        "workflow",
        "compare",
        inputs={"original_document": _document(original)},
    ))

    assert result.status == NodeStatus.FAILURE
    assert "Document to compare" in (result.error or "")
