from __future__ import annotations

from pathlib import Path
from typing import Any

_TABLE_MODEL_ID = "microsoft/table-transformer-detection"
_STRUCTURE_MODEL_ID = "microsoft/table-transformer-structure-recognition"


class TableExtractionService:
    """Detects tables in a page image and extracts their row/column structure
    using Microsoft's Table Transformer models."""

    def __init__(self):
        self._detection_model = None
        self._structure_model = None
        self._image_processor = None

    def _load_models(self):
        if self._detection_model is not None:
            return

        from transformers import AutoImageProcessor, TableTransformerForObjectDetection

        self._image_processor = AutoImageProcessor.from_pretrained(_TABLE_MODEL_ID)
        self._detection_model = TableTransformerForObjectDetection.from_pretrained(_TABLE_MODEL_ID)
        self._structure_model = TableTransformerForObjectDetection.from_pretrained(_STRUCTURE_MODEL_ID)

    async def extract(self, image_path: str | Path, confidence_threshold: float = 0.7) -> dict[str, Any]:
        import torch
        from PIL import Image

        self._load_models()

        image = Image.open(image_path).convert("RGB")

        # Step 1: detect table bounding boxes on the page
        inputs = self._image_processor(images=image, return_tensors="pt")
        with torch.no_grad():
            outputs = self._detection_model(**inputs)

        target_sizes = torch.tensor([image.size[::-1]])
        detections = self._image_processor.post_process_object_detection(
            outputs, threshold=confidence_threshold, target_sizes=target_sizes
        )[0]

        tables: list[dict[str, Any]] = []

        for score, label, box in zip(detections["scores"], detections["labels"], detections["boxes"]):
            box_coords = [round(v, 2) for v in box.tolist()]
            cropped = image.crop(box_coords)

            structure = self._extract_structure(cropped, confidence_threshold)

            tables.append({
                "bbox": box_coords,
                "confidence": round(score.item(), 4),
                "rows": structure["row_count"],
                "columns": structure["column_count"],
                "cells": structure["cells"],
            })

        return {
            "tables": tables,
            "table_count": len(tables),
        }

    def _extract_structure(self, table_image, confidence_threshold: float) -> dict[str, Any]:
        import torch

        inputs = self._image_processor(images=table_image, return_tensors="pt")
        with torch.no_grad():
            outputs = self._structure_model(**inputs)

        target_sizes = torch.tensor([table_image.size[::-1]])
        detections = self._image_processor.post_process_object_detection(
            outputs, threshold=confidence_threshold, target_sizes=target_sizes
        )[0]

        id2label = self._structure_model.config.id2label
        rows = []
        columns = []
        cells = []

        for label_id, box in zip(detections["labels"].tolist(), detections["boxes"].tolist()):
            label = id2label.get(label_id, "")
            entry = {"bbox": [round(v, 2) for v in box]}
            if "row" in label:
                rows.append(entry)
            elif "column" in label:
                columns.append(entry)
            elif "cell" in label:
                cells.append(entry)

        return {
            "row_count": len(rows),
            "column_count": len(columns),
            "cells": cells,
        }