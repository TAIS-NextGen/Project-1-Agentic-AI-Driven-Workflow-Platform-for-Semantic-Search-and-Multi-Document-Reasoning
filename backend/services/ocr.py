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
        try:
            import os
            import pytesseract
            from PIL import Image
            from backend.settings import settings

            # Resolve Tesseract path: prioritize settings first, then fallback to Windows defaults
            tesseract_path = settings.ocr_tesseract_path.strip()
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            elif os.name == "nt" and not getattr(pytesseract.pytesseract, "tesseract_cmd", None):
                default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                if os.path.exists(default_path):
                    pytesseract.pytesseract.tesseract_cmd = default_path
                else:
                    # Let's also check default local appdata path if installed user-only
                    local_appdata_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")
                    if os.path.exists(local_appdata_path):
                        pytesseract.pytesseract.tesseract_cmd = local_appdata_path

            with Image.open(image_path) as img:
                osd = pytesseract.image_to_osd(img)
                angle = 0
                confidence = 1.0
                for line in osd.split("\n"):
                    if "Rotate:" in line:
                        try:
                            angle = int(line.split(":")[1].strip())
                        except ValueError:
                            pass
                    elif "Orientation confidence:" in line:
                        try:
                            confidence = float(line.split(":")[1].strip())
                        except ValueError:
                            pass
                return {"angle": angle, "confidence": confidence}
        except Exception as e:
            logger.warning(
                f"Orientation detection failed (pytesseract OSD failed or not installed): {e}. "
                "Returning default (0 degrees)."
            )
            return {"angle": 0, "confidence": 1.0}


class TesseractOCRService:
    """Printed-text OCR using Tesseract — fast, no GPU, good first-pass
    baseline for typed/scanned documents (as opposed to handwriting)."""

    def __init__(self, lang: str = "eng"):
        self.lang = lang

    async def extract_text(
        self, image_path: str | Path, lang: str | None = None
    ) -> dict[str, Any]:
        import pytesseract
        from PIL import Image

        active_lang = lang or self.lang
        image = Image.open(image_path)

        data = pytesseract.image_to_data(
            image, lang=active_lang, output_type=pytesseract.Output.DICT
        )

        lines: list[dict[str, Any]] = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if not text:
                continue
            conf_raw = data["conf"][i]
            confidence = float(conf_raw) / 100 if conf_raw not in ("-1", -1) else 0.0
            lines.append({"text": text, "confidence": round(confidence, 4)})

        full_text = " ".join(l["text"] for l in lines)
        avg_conf = (
            round(sum(l["confidence"] for l in lines) / len(lines), 4)
            if lines
            else 0.0
        )

        return {
            "text": full_text,
            "confidence": avg_conf,
            "lines": lines,
            "total_lines": len(lines),
        }

    async def extract_text_from_pdf(
        self, pdf_path: str | Path, lang: str | None = None, dpi: int = 300
    ) -> dict[str, Any]:
        from pdf2image import convert_from_path

        pages = convert_from_path(str(pdf_path), dpi=dpi)
        all_lines: list[dict[str, Any]] = []
        page_texts: list[str] = []

        for page_image in pages:
            page_image.save("/tmp/_tesseract_page_tmp.png")
            page_result = await self.extract_text("/tmp/_tesseract_page_tmp.png", lang)
            page_texts.append(page_result["text"])
            all_lines.extend(page_result["lines"])

        full_text = "\n\n".join(page_texts)
        avg_conf = (
            round(sum(l["confidence"] for l in all_lines) / len(all_lines), 4)
            if all_lines
            else 0.0
        )

        return {
            "text": full_text,
            "confidence": avg_conf,
            "lines": all_lines,
            "total_lines": len(all_lines),
            "total_pages": len(pages),
        }
