from __future__ import annotations

from pathlib import Path
from typing import Any

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


class WatermarkRemovalService:
    """Removes watermarks from images (inpainting) and PDFs
    (OCG layer stripping, with a rasterized-inpaint fallback)."""

    def __init__(self, inpaint_radius: int = 3):
        self.inpaint_radius = inpaint_radius

    async def remove(self, input_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ext = input_path.suffix.lower()

        if ext == ".pdf":
            return await self._remove_from_pdf(input_path, output_dir)
        if ext in _IMAGE_EXTENSIONS:
            return await self._remove_from_image(input_path, output_dir)

        raise ValueError(f"Unsupported file extension for watermark removal: {ext}")

    async def _remove_from_image(self, input_path: Path, output_dir: Path) -> dict[str, Any]:
        import cv2
        import numpy as np

        img = cv2.imread(str(input_path))
        if img is None:
            raise RuntimeError(f"Could not read image: {input_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        cleaned = cv2.inpaint(img, mask, self.inpaint_radius, cv2.INPAINT_TELEA)

        output_path = output_dir / f"{input_path.stem}_cleaned{input_path.suffix}"
        cv2.imwrite(str(output_path), cleaned)

        return {
            "output_path": str(output_path),
            "method": "inpaint",
            "watermark_coverage": float(mask.mean() / 255),
        }

    async def _remove_from_pdf(self, input_path: Path, output_dir: Path) -> dict[str, Any]:
        import fitz  # PyMuPDF

        doc = fitz.open(str(input_path))
        watermark_xrefs = []

        for xref, info in doc.get_ocgs().items():
            name = (info.get("name") or "").lower()
            if "watermark" in name or "stamp" in name:
                watermark_xrefs.append(xref)

        if not watermark_xrefs:
            doc.close()
            return await self._remove_from_pdf_rasterized(input_path, output_dir)

        doc.set_layer(-1, off=watermark_xrefs)

        output_path = output_dir / f"{input_path.stem}_cleaned.pdf"
        doc.save(str(output_path), garbage=4, deflate=True)
        doc.close()

        return {"output_path": str(output_path), "method": "ocg_removal", "layers_removed": len(watermark_xrefs)}
    async def _remove_from_pdf_rasterized(self, input_path: Path, output_dir: Path) -> dict[str, Any]:
        import fitz
        import cv2
        import numpy as np

        src = fitz.open(str(input_path))
        out = fitz.open()

        for page in src:
            pix = page.get_pixmap(dpi=200)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR if pix.n == 4 else cv2.COLOR_RGB2BGR)

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
            cleaned = cv2.inpaint(img, mask, self.inpaint_radius, cv2.INPAINT_TELEA)

            _, buf = cv2.imencode(".png", cleaned)
            new_page = out.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(page.rect, stream=buf.tobytes())

        src.close()
        output_path = output_dir / f"{input_path.stem}_cleaned.pdf"
        out.save(str(output_path))
        out.close()

        return {"output_path": str(output_path), "method": "rasterized_inpaint"}