from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.sdk import BaseNode, ConfigField, ExecutionContext, NodeResult, Port, PortType
from backend.services.watermark_removal import WatermarkRemovalService


class WatermarkRemoverNode(BaseNode):
    type = "watermark-remover"
    name = "Watermark Remover"
    category = "ingestion"
    icon = "🧽"
    color = "#3b82f6"
    description = "Remove watermarks from images or PDFs"
    version = "1.0.0"

    inputs = [
        Port(name="document", type=PortType.DOCUMENT, label="Document/Image",
             description="Source PDF or image containing a watermark", required=True),
    ]

    outputs = [
        Port(name="cleaned_document", type=PortType.DOCUMENT, label="Cleaned Document",
             description="Path to the watermark-free output file"),
    ]

    config_fields = [
        ConfigField(key="inpaint_radius", label="Inpaint Radius", type="number",
                    required=False, default=3,
                    description="Pixel radius used when filling in removed watermark regions"),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()
        try:
            config = self.get_resolved_config()
            file_data: dict[str, Any] | None = ctx.get_input("document")
            if not file_data:
                result.fail("No document provided")
                return result

            file_path = Path(file_data["path"])
            if not file_path.exists():
                result.fail(f"File not found at path: {file_path}")
                return result

            service = WatermarkRemovalService(inpaint_radius=int(config.get("inpaint_radius", 3)))
            output_dir = Path(os.getenv("UPLOAD_DIR", "data/uploads")) / "cleaned"
            removal = await service.remove(file_path, output_dir)

            result.succeed({"cleaned_document": removal["output_path"]})
        except Exception as e:
            result.fail(str(e))
        return result