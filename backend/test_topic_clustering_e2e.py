"""Standalone end-to-end test for Corpus Input -> Topic Clustering."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from backend.nodes.clustering.corpus_input import CorpusInputNode
from backend.nodes.clustering.topic_clustering import TopicClusteringNode
from backend.sdk import ExecutionContext, NodeStatus


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        samples = {
            "finance/budget.txt": "budget finance invoice accounting revenue profit tax",
            "finance/invoice.txt": "invoice payment accounting supplier finance tax",
            "health/clinic.txt": "doctor patient clinic hospital medicine treatment",
            "health/pharmacy.txt": "medicine pharmacy patient treatment health hospital",
        }
        documents = []
        for index, (relative_path, text) in enumerate(samples.items(), start=1):
            path = root / f"doc-{index}.txt"
            path.write_text(text, encoding="utf-8")
            documents.append({
                "file_id": str(index),
                "filename": Path(relative_path).name,
                "relative_path": relative_path,
                "path": str(path),
                "extension": ".txt",
                "size_bytes": path.stat().st_size,
            })

        corpus_node = CorpusInputNode("corpus", {
            "folder_name": "demo",
            "file_ids": [item["file_id"] for item in documents],
            "documents": documents,
        })
        corpus_result = asyncio.run(corpus_node.execute(ExecutionContext("demo", "corpus")))
        if corpus_result.status != NodeStatus.SUCCESS:
            print(f"[FAIL] Corpus Input: {corpus_result.error}")
            return 1

        clustering_node = TopicClusteringNode("clustering", {
            "number_of_clusters": 2,
            "create_downloads": False,
        })
        clustering_result = asyncio.run(clustering_node.execute(ExecutionContext(
            "demo",
            "clustering",
            inputs={"corpus": corpus_result.outputs["corpus"]},
        )))
        if clustering_result.status != NodeStatus.SUCCESS:
            print(f"[FAIL] Topic Clustering: {clustering_result.error}")
            return 1

        print(f"[PASS] {len(clustering_result.outputs['clusters'])} clusters")
        for cluster in clustering_result.outputs["clusters"]:
            names = ", ".join(item["filename"] for item in cluster["documents"])
            print(f"  - {cluster['label']}: {names}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
