"""Standalone smoke test for Contrast Enhancer."""
import asyncio
import sys
import tempfile
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def main() -> int:
    from PIL import Image
    from backend.nodes.preprocessing.contrast_enhancer import ContrastEnhancerNode
    from backend.sdk import ExecutionContext, NodeStatus

    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "scan.png"
        Image.new("RGB", (160, 100), (125, 125, 125)).save(source)
        node = ContrastEnhancerNode("contrast-e2e", {"contrast": 1.5, "brightness": 1.1})
        ctx = ExecutionContext(
            workflow_id="e2e",
            node_id="contrast-e2e",
            inputs={"image": {"filename": source.name, "path": str(source), "size_bytes": source.stat().st_size}},
            config={},
        )
        result = asyncio.run(node.execute(ctx))
        if result.status != NodeStatus.SUCCESS:
            print(f"[FAIL] {result.error}")
            return 1
        print(f"[PASS] Enhanced image: {result.outputs['image']['path']}")
        print(f"[PASS] Metadata: {result.outputs['metadata']}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
