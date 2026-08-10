from __future__ import annotations

from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)
from backend.services.barcode_reader import BarcodeReaderService


class BarcodeReaderNode(BaseNode):
    type = "barcode-reader"
    name = "Barcode & QR Reader"
    category = "extraction"
    icon = "🔳"
    color = "#ec4899"
    description = "Detect and decode barcodes and QR codes from images"
    version = "1.0.0"

    inputs = [
        Port(
            name="image",
            type=PortType.IMAGE,
            label="Image",
            description="The image containing the barcodes or QR codes",
            required=True,
        ),
    ]

    outputs = [
        Port(
            name="barcodes_data",
            type=PortType.JSON,
            label="Barcodes Data",
            description="Structured JSON data containing the types, decoded text, and coordinates of all detected codes",
        ),
        Port(
            name="annotated_image",
            type=PortType.IMAGE,
            label="Annotated Image",
            description="The original image with bounding boxes drawn around detected codes",
        ),
        Port(
            name="text",
            type=PortType.TEXT,
            label="Extracted Text",
            description="The combined decoded text from all detected codes, separated by newlines",
        ),
    ]

    config_fields = [
        ConfigField(
            key="draw_boxes",
            label="Draw Bounding Boxes",
            type="boolean",
            required=False,
            default=True,
            description="If true, generates an output image with green boxes highlighting detected codes",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            draw_boxes = config.get("draw_boxes", True)

            image_input = ctx.get_input("image")
            
            # Handle both raw string paths and rich document dictionaries
            image_path = ""
            if isinstance(image_input, dict) and "path" in image_input:
                image_path = image_input["path"]
            elif isinstance(image_input, str):
                image_path = image_input

            if not image_path or not image_path.strip():
                result.fail("No valid image provided to the Barcode Reader node")
                return result

            service = BarcodeReaderService()
            barcodes, annotated_path = service.detect_and_decode(image_path=image_path, draw_boxes=draw_boxes)

            # Combine all decoded text into a single string
            extracted_text = "\n".join(b["data"] for b in barcodes) if barcodes else ""

            result.succeed({
                "barcodes_data": barcodes,
                "annotated_image": annotated_path,
                "text": extracted_text,
            })

        except Exception as e:
            result.fail(f"Barcode Reader node execution failed: {e}")

        return result
