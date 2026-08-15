from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)
from backend.services.image_agent import ImageAgentService


class ImageAgentNode(BaseNode):
    type = "image-agent"
    name = "Image Agent"
    category = "agents"
    icon = "\U0001f5bc\ufe0f"
    color = "#a855f7"
    description = "Analyse graphs, diagrams, and images using visual AI (Moondream2 or LLaVA)"
    version = "1.0.0"

    inputs = [
        Port(
            name="image",
            type=PortType.IMAGE,
            label="Image",
            description="Image to analyze (graph, diagram, document, photo)",
            required=True,
        ),
    ]

    outputs = [
        Port(
            name="interpretation",
            type=PortType.TEXT,
            label="Interpretation",
            description="Visual analysis result in natural language",
        ),
    ]

    config_fields = [
        ConfigField(
            key="model",
            label="Vision Model",
            type="select",
            required=False,
            default="moondream:latest",
            options=["moondream:latest", "llava:7b"],
            description="Vision model: moondream (fast, small) or llava (accurate, larger)",
        ),
        ConfigField(
            key="language",
            label="Language",
            type="select",
            required=False,
            default="en",
            options=["fr", "en", "ar"],
            description="Language for the analysis response",
        ),
        ConfigField(
            key="question",
            label="Question",
            type="text",
            required=False,
            default="Describe this image in detail.",
            description="Question or instruction for the vision model",
        ),
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID from /api/documents/upload. Leave empty if image comes from upstream node.",
        ),
    ]

    @staticmethod
    def _get_upload_dir() -> Path:
        return Path(os.getenv("UPLOAD_DIR", "data/uploads"))

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            model = config.get("model", "moondream:latest")
            language = config.get("language", "en")

            image_data: dict[str, Any] | None = ctx.get_input("image")
            if not image_data:
                file_id = config.get("file_id", "")
                if file_id:
                    image_data = await self._resolve_by_file_id(file_id)
            if not image_data:
                result.fail("No image provided. Connect a DocumentUpload node upstream or set a File ID in config.")
                return result

            path_val = image_data.get("path") or image_data.get("file_path")
            if not path_val:
                result.fail("No file path found in input data")
                return result

            image_path = Path(path_val)
            if not image_path.exists():
                result.fail(f"Image not found at path: {image_path}")
                return result

            question = config.get("question", "Describe this image in detail.")

            service = ImageAgentService(model=model)
            interpretation = await service.analyze(
                image_path=str(image_path),
                question=question,
                language=language,
            )

            result.succeed({"interpretation": interpretation})

        except Exception as e:
            result.fail(str(e))

        return result

    async def _resolve_by_file_id(self, file_id: str) -> dict[str, Any] | None:
        upload_dir = self._get_upload_dir()
        if not upload_dir.exists():
            return None
        index_path = upload_dir / ".documents-index.json"
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
                record = index.get(file_id) if isinstance(index, dict) else None
                if record:
                    file_path = Path(record.get("path", ""))
                    if file_path.exists():
                        return {
                            "file_id": file_id,
                            "filename": record.get("filename", file_path.name),
                            "path": str(file_path),
                            "size_bytes": record.get("size_bytes", file_path.stat().st_size),
                            "mime_type": record.get("mime_type"),
                        }
            except (OSError, json.JSONDecodeError):
                pass
        for f in upload_dir.iterdir():
            if f.is_file() and not f.name.startswith(".") and f.stem == file_id:
                return {
                    "file_id": file_id,
                    "filename": f.name,
                    "path": str(f),
                    "size_bytes": f.stat().st_size,
                }
        return None
