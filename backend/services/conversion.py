from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_OFFICE_EXTENSIONS = {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".odt"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


class FileConversionService:
    """Converts office documents and images into PDF or plain text.
    Office formats are converted via headless LibreOffice; images via Pillow."""

    def __init__(self, soffice_bin: str | None = None):
        self.soffice_bin = soffice_bin or shutil.which("libreoffice") or shutil.which("soffice")

    async def convert_to_pdf(self, input_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ext = input_path.suffix.lower()

        if ext == ".pdf":
            return {"output_path": str(input_path), "converted": False, "reason": "already PDF"}

        if ext in _IMAGE_EXTENSIONS:
            return await self._image_to_pdf(input_path, output_dir)

        if ext in _OFFICE_EXTENSIONS:
            return await self._office_to_pdf(input_path, output_dir)

        raise ValueError(f"Unsupported file extension for PDF conversion: {ext}")

    async def _office_to_pdf(self, input_path: Path, output_dir: Path) -> dict[str, Any]:
        if not self.soffice_bin:
            raise RuntimeError(
                "LibreOffice not found on this system. Install it (e.g. `sudo dnf install libreoffice`) "
                "to convert office documents."
            )

        cmd = [
            self.soffice_bin,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            str(input_path),
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed: {stderr.decode(errors='replace')}")

        output_path = output_dir / f"{input_path.stem}.pdf"
        if not output_path.exists():
            raise RuntimeError(f"Expected output file not found: {output_path}")

        return {"output_path": str(output_path), "converted": True}

    async def _image_to_pdf(self, input_path: Path, output_dir: Path) -> dict[str, Any]:
        from PIL import Image

        output_path = output_dir / f"{input_path.stem}.pdf"
        image = Image.open(input_path)
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(output_path, "PDF")

        return {"output_path": str(output_path), "converted": True}

    async def extract_text(self, input_path: str | Path) -> dict[str, Any]:
        input_path = Path(input_path)
        ext = input_path.suffix.lower()

        if ext == ".docx":
            return await self._extract_docx_text(input_path)

        raise ValueError(f"Text extraction not supported for extension: {ext}")

    async def _extract_docx_text(self, input_path: Path) -> dict[str, Any]:
        import docx

        document = docx.Document(str(input_path))
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        full_text = "\n".join(paragraphs)

        return {"text": full_text, "paragraph_count": len(paragraphs)}