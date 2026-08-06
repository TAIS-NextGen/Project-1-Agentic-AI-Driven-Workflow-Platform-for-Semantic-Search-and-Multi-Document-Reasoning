"""Standalone smoke test for Document Parser."""
import asyncio
import sys
import tempfile
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def main() -> int:
    from openpyxl import Workbook
    from backend.nodes.ingestion.document_parser import DocumentParserNode
    from backend.sdk import ExecutionContext, NodeStatus

    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "data.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Data"
        sheet.append(["Name", "Score"])
        sheet.append(["Ayoub", 95])
        workbook.save(source)

        node = DocumentParserNode("parser-e2e", {})
        ctx = ExecutionContext(
            workflow_id="e2e",
            node_id="parser-e2e",
            inputs={"document": {"filename": source.name, "path": str(source), "size_bytes": source.stat().st_size}},
            config={},
        )
        result = asyncio.run(node.execute(ctx))
        if result.status != NodeStatus.SUCCESS:
            print(f"[FAIL] {result.error}")
            return 1
        print("[PASS] Extracted text:")
        print(result.outputs["text"])
        print(f"[PASS] Metadata: {result.outputs['metadata']}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
