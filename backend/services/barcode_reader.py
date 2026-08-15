import logging
import uuid
import cv2
import numpy as np
from pathlib import Path
from typing import Any
from pyzbar import pyzbar

from backend.settings import settings

logger = logging.getLogger(__name__)

class BarcodeReaderService:
    def detect_and_decode(self, image_path: str, draw_boxes: bool = True) -> tuple[list[dict[str, Any]], str]:
        """
        Reads an image and detects all barcodes and QR codes using pyzbar.
        Returns:
            - A list of dictionaries with decoded data and coordinates.
            - The file path to the annotated image (if draw_boxes=True, else original path).
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found at {image_path}")

        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to read image at {image_path}. Ensure it is a valid image file.")

        decoded_objects = pyzbar.decode(image)
        results = []

        annotated_image = image.copy() if draw_boxes else image

        for obj in decoded_objects:
            data = obj.data.decode("utf-8")
            code_type = obj.type
            
            # Bounding box is (left, top, width, height)
            x, y, w, h = obj.rect
            rect = {"left": x, "top": y, "width": w, "height": h}
            
            # Polygon points
            polygon = [{"x": p.x, "y": p.y} for p in obj.polygon]

            results.append({
                "type": code_type,
                "data": data,
                "rect": rect,
                "polygon": polygon
            })

            if draw_boxes:
                # Draw the bounding box polygon in green (BGR: 0, 255, 0)
                points = np.array([[p.x, p.y] for p in obj.polygon], np.int32)
                points = points.reshape((-1, 1, 2))
                cv2.polylines(annotated_image, [points], True, (0, 255, 0), 3)

                # Put the decoded text near the box (blue)
                cv2.putText(
                    annotated_image, 
                    data, 
                    (x, max(0, y - 10)), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.5, 
                    (255, 0, 0), 
                    2
                )

        output_path = image_path
        if draw_boxes and results:
            storage_dir = Path(settings.storage_dir)
            storage_dir.mkdir(parents=True, exist_ok=True)
            output_name = f"barcode_annotated_{uuid.uuid4().hex[:8]}.png"
            output_path = str(storage_dir / output_name)
            cv2.imwrite(output_path, annotated_image)

        return results, output_path
