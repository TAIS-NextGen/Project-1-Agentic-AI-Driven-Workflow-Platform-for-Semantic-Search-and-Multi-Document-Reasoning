"""Standalone smoke test for the Masker node."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def main() -> int:
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf  # type: ignore

    from backend.nodes.preprocessing.masker import MaskerNode
    from backend.sdk import ExecutionContext, NodeStatus

    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary = Path(temporary_directory)
        source = temporary / "masker-sample.pdf"
        storage = temporary / "storage"
        os.environ["STORAGE_DIR"] = str(storage)

        document = pymupdf.open()
        page = document.new_page()
        page.insert_text((72, 72), "Email: user@example.com")
        page.insert_text((72, 96), "Phone: +33 6 12 34 56 78")
        page.insert_text((72, 120), "CIN: AB123456")
        document.save(source)
        document.close()

        node = MaskerNode("masker-e2e", {})
        context = ExecutionContext(
            workflow_id="masker-e2e",
            node_id="masker-e2e",
            inputs={
                "document": {
                    "filename": source.name,
                    "path": str(source),
                    "mime_type": "application/pdf",
                    "size_bytes": source.stat().st_size,
                }
            },
        )
        result = asyncio.run(node.execute(context))
        if result.status != NodeStatus.SUCCESS:
            print(f"[FAIL] {result.error}")
            return 1

        output = Path(result.outputs["document"]["path"])
        print(f"[PASS] Masked PDF: {output}")
        print(f"[PASS] Report: {result.outputs['report']}")
        return 0 if output.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
