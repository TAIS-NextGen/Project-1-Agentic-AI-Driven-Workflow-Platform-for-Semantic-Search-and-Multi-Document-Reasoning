from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self, lang: str = "ar"):
        self.lang = lang
        self._reader = None

    def _get_reader(self):
        if self._reader is None:
            try:
                import easyocr

                lang_list = [l.strip() for l in self.lang.split(",") if l.strip()]
                self._reader = easyocr.Reader(
                    lang_list,
                    gpu=False,
                )
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                raise
        return self._reader

    async def extract_text(self, image_path: str | Path, lang: str | None = None) -> dict[str, Any]:
        if lang:
            self.lang = lang
            self._reader = None

        reader = self._get_reader()
        result = reader.readtext(str(image_path))

        lines = []
        for bbox, text, confidence in result:
            lines.append({"text": text, "confidence": round(confidence, 4)})

        full_text = "\n".join(l["text"] for l in lines)
        avg_conf = round(sum(l["confidence"] for l in lines) / len(lines), 4) if lines else 0

        return {
            "text": full_text,
            "confidence": avg_conf,
            "lines": lines,
            "total_lines": len(lines),
        }

    async def extract_tables(self, image_path: str | Path) -> list[list[list[str]]]:
        logger.warning("OCRService.extract_tables() not implemented — using mock")
        return [[["Mock", "Table", "Data"]]]

    async def detect_orientation(self, image_path: str | Path) -> dict[str, Any]:
        return {"angle": 0, "confidence": 1.0}
