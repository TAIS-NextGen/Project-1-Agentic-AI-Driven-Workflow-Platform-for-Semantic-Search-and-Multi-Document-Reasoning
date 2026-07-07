from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self, tesseract_path: str = "", languages: str = "eng+fra"):
        self.tesseract_path = tesseract_path
        self.languages = languages

    async def extract_text(self, image_path: str | Path, lang: str | None = None) -> str:
        logger.warning("OCRService.extract_text() not implemented — using mock")
        return f"[Mock OCR text extracted from: {Path(image_path).name}]"

    async def extract_tables(self, image_path: str | Path) -> list[list[list[str]]]:
        logger.warning("OCRService.extract_tables() not implemented — using mock")
        return [[["Mock", "Table", "Data"]]]

    async def detect_orientation(self, image_path: str | Path) -> dict[str, Any]:
        return {"angle": 0, "confidence": 1.0}
