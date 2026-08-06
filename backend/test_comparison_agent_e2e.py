"""Standalone smoke test for the Comparison Agent node."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.nodes.agents.comparison_agent import ComparisonAgentNode
from backend.sdk import ExecutionContext, NodeStatus


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        os.environ["STORAGE_DIR"] = str(root / "storage")
        original = root / "version-1.txt"
        revised = root / "version-2.txt"
        original.write_text("Title\nAmount: 100 EUR\nStatus: draft\n", encoding="utf-8")
        revised.write_text("Title\nAmount: 150 EUR\nStatus: approved\n", encoding="utf-8")

        node = ComparisonAgentNode("comparison", {})
        result = asyncio.run(node.execute(ExecutionContext(
            "comparison-demo",
            "comparison",
            inputs={
                "original_document": {"filename": original.name, "path": str(original)},
                "revised_document": {"filename": revised.name, "path": str(revised)},
            },
        )))
        if result.status != NodeStatus.SUCCESS:
            print(f"[FAIL] {result.error}")
            return 1

        summary = result.outputs["summary"]
        print(f"[PASS] Similarity: {summary['similarity_percent']}%")
        print(f"[PASS] Change blocks: {summary['change_block_count']}")
        print(f"[PASS] HTML report: {result.outputs['downloads']['html']['path']}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
