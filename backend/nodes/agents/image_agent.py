from __future__ import annotations

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
            description="Question to ask about the image",
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
                result.fail("No image provided. Connect a DocumentUpload node upstream.")
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
