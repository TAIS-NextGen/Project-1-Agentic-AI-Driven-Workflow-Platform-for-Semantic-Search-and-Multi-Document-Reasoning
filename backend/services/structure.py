from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.settings import settings

logger = logging.getLogger(__name__)


class StructureAnalyzerService:
    async def analyze(self, file_path: str | Path, strategy: str = "auto", languages: str = "ara+eng+fra") -> dict[str, Any]:
        self._ensure_tesseract()

        from unstructured.partition.auto import partition

        ocr_languages = [lang.strip() for lang in languages.split("+") if lang.strip()]
        elements = partition(
            filename=str(file_path),
            strategy=strategy,
            languages=ocr_languages,
            include_page_breaks=True,
        )

        pages: dict[int, list[dict]] = {}
        current_page = 0

        for el in elements:
            el_dict = el.to_dict()

            if el_dict.get("type") == "PageBreak":
                continue

            page_number = el.metadata.page_number
            if page_number is not None:
                current_page = page_number - 1 if page_number > 0 else 0

            if current_page not in pages:
                pages[current_page] = []

            el_type = el_dict.get("type", "UncategorizedText")
            mapped_type = self._map_element_type(el_type)

            coords = el.metadata.coordinates
            bbox = {}
            if coords and hasattr(coords, 'points'):
                pts = coords.points
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if xs and ys:
                    bbox = {
                        "xmin": round(min(xs), 4),
                        "ymin": round(min(ys), 4),
                        "xmax": round(max(xs), 4),
                        "ymax": round(max(ys), 4),
                    }

            text = el_dict.get("text", "")

            region = {
                "type": mapped_type,
                "text": text if text else "",
                "confidence": 0.9,
                "bbox": bbox,
                "word_count": len(text.split()) if text else 0,
            }

            table_html = el.metadata.text_as_html
            if table_html:
                region["table_html"] = table_html

            pages[current_page].append(region)

        page_list = [
            {
                "page_idx": idx,
                "layout": pages[idx],
            }
            for idx in sorted(pages.keys())
        ]

        return {
            "pages": page_list,
            "summary": self._build_summary(page_list),
        }

    @staticmethod
    def _ensure_tesseract():
        path = settings.ocr_tesseract_path.strip()
        if not path:
            return
        try:
            import unstructured_pytesseract

            unstructured_pytesseract.pytesseract.tesseract_cmd = path
        except ImportError:
            pass
        try:
            import pytesseract

            pytesseract.pytesseract.tesseract_cmd = path
        except ImportError:
            pass

    @staticmethod
    def _map_element_type(unstructured_type: str) -> str:
        mapping = {
            "Title": "Title",
            "NarrativeText": "Text",
            "Text": "Text",
            "UncategorizedText": "Text",
            "Table": "Table",
            "Image": "Figure",
            "FigureCaption": "Caption",
            "Header": "Page-header",
            "Footer": "Page-footer",
            "ListItem": "List-item",
            "Formula": "Formula",
            "CodeSnippet": "Code",
            "PageNumber": "PageNumber",
            "Address": "Address",
            "EmailAddress": "Email",
        }
        return mapping.get(unstructured_type, "Text")

    @staticmethod
    def _build_summary(pages: list[dict]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for page in pages:
            for region in page["layout"]:
                t = region["type"]
                counts[t] = counts.get(t, 0) + 1
        return {
            "total_pages": len(pages),
            "total_elements": sum(counts.values()),
            "elements_by_type": counts,
        }
