from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.nodes.clustering.corpus_input import CorpusInputNode
from backend.nodes.clustering.topic_clustering import TopicClusteringNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.mark.asyncio
async def test_corpus_input_returns_all_configured_documents(tmp_path: Path):
    documents = []
    for relative_path, content in [
        ("finance/budget.txt", "budget finance invoice accounting revenue"),
        ("health/clinic.txt", "doctor patient hospital medicine health"),
    ]:
        path = tmp_path / Path(relative_path).name
        path.write_text(content, encoding="utf-8")
        documents.append({
            "file_id": path.stem,
            "filename": path.name,
            "relative_path": relative_path,
            "path": str(path),
            "mime_type": "text/plain",
            "extension": ".txt",
            "size_bytes": path.stat().st_size,
        })

    node = CorpusInputNode("corpus", {
        "folder_name": "sample-corpus",
        "file_ids": [document["file_id"] for document in documents],
        "documents": documents,
    })
    result = await node.execute(ExecutionContext("workflow", "corpus"))

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["corpus"]["name"] == "sample-corpus"
    assert result.outputs["corpus"]["document_count"] == 2
    assert {item["relative_path"] for item in result.outputs["documents"]} == {
        "finance/budget.txt",
        "health/clinic.txt",
    }


@pytest.mark.asyncio
async def test_topic_clustering_groups_documents_and_creates_downloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    storage = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_DIR", str(storage))

    samples = {
        "finance/budget.txt": "budget finance accounting invoice revenue profit tax budget finance accounting",
        "finance/invoice.txt": "invoice payment supplier accounting amount tax finance invoice payment",
        "finance/report.txt": "financial revenue profit budget accounting company finance revenue",
        "health/clinic.txt": "doctor patient hospital clinic medicine health treatment doctor patient",
        "health/medicine.txt": "medicine pharmacy treatment patient health hospital medicine doctor",
        "health/care.txt": "healthcare clinic nurse doctor patient hospital treatment health",
    }
    documents = []
    for index, (relative_path, content) in enumerate(samples.items(), start=1):
        path = tmp_path / f"document-{index}.txt"
        path.write_text(content, encoding="utf-8")
        documents.append({
            "file_id": f"file-{index}",
            "filename": Path(relative_path).name,
            "relative_path": relative_path,
            "path": str(path),
            "mime_type": "text/plain",
            "extension": ".txt",
            "size_bytes": path.stat().st_size,
        })

    node = TopicClusteringNode("cluster", {
        "number_of_clusters": 2,
        "max_automatic_clusters": 8,
        "create_downloads": True,
    })
    result = await node.execute(ExecutionContext(
        workflow_id="workflow",
        node_id="cluster",
        inputs={"corpus": {"name": "sample-corpus", "documents": documents}},
    ))

    assert result.status == NodeStatus.SUCCESS, result.error
    clusters = result.outputs["clusters"]
    assert len(clusters) == 2
    assert sum(cluster["document_count"] for cluster in clusters) == 6

    assignment_by_file = {
        assignment["relative_path"]: assignment["cluster_id"]
        for assignment in result.outputs["assignments"]
    }
    finance_clusters = {assignment_by_file[path] for path in samples if path.startswith("finance/")}
    health_clusters = {assignment_by_file[path] for path in samples if path.startswith("health/")}
    assert len(finance_clusters) == 1
    assert len(health_clusters) == 1
    assert finance_clusters != health_clusters

    downloads = result.outputs["downloads"]
    assert Path(downloads["json"]["path"]).exists()
    assert Path(downloads["csv"]["path"]).exists()
    assert Path(downloads["bundle"]["path"]).exists()


@pytest.mark.asyncio
async def test_topic_clustering_reports_unsupported_and_empty_documents(tmp_path: Path):
    valid = tmp_path / "valid.txt"
    valid.write_text("project management planning roadmap delivery milestone project", encoding="utf-8")
    empty = tmp_path / "empty.txt"
    empty.write_text(" ", encoding="utf-8")
    unsupported = tmp_path / "archive.bin"
    unsupported.write_bytes(b"binary")

    documents = [
        {"filename": valid.name, "path": str(valid), "relative_path": valid.name},
        {"filename": empty.name, "path": str(empty), "relative_path": empty.name},
        {"filename": unsupported.name, "path": str(unsupported), "relative_path": unsupported.name},
    ]
    node = TopicClusteringNode("cluster", {"number_of_clusters": 1, "create_downloads": False})
    result = await node.execute(ExecutionContext("workflow", "cluster", inputs={"corpus": {"documents": documents}}))

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["metadata"]["clustered_document_count"] == 1
    assert result.outputs["metadata"]["skipped_document_count"] == 2
    assert len(result.outputs["clusters"]) == 1
