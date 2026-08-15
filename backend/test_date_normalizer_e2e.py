"""Manual end-to-end check for the real DateParser dependency.

Run from the project root after run.bat has installed dependencies:
    .venv\\Scripts\\python.exe backend\test_date_normalizer_e2e.py
"""

from __future__ import annotations

import asyncio
import json

from backend.nodes.normalization.date_normalizer import DateNormalizerNode
from backend.sdk import ExecutionContext, NodeStatus


async def main() -> None:
    sample = "The meeting is tomorrow at 10:30. Le prochain contrôle est prévu le 12/08/2026."
    node = DateNormalizerNode(
        "date-normalizer-demo",
        {"output_format": "YYYY-MM-DD", "replace_in_text": True},
    )
    result = await node.execute(
        ExecutionContext(
            workflow_id="manual-date-test",
            node_id=node.node_id,
            inputs={"text": sample},
            config=node.get_resolved_config(),
        )
    )

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
    if result.status != NodeStatus.SUCCESS:
        raise SystemExit(1)
    if not result.outputs.get("dates"):
        raise SystemExit("The node succeeded but no date was detected in the sample.")


if __name__ == "__main__":
    asyncio.run(main())
