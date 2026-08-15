from __future__ import annotations

import os
import threading
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

_ocr_cache: dict[str, Any] = {}
_ocr_lock = threading.Lock()


def _get_paddle_ocr(language: str, use_angle: bool, model_size: str = "mobile"):
    """Return a cached PaddleOCR instance. Model loading is expensive on CPU,
    so cache per (language, use_angle, model_size) key and reuse across documents."""
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    from paddleocr import PaddleOCR

    key = f"{language}|{use_angle}|{model_size}"

    if model_size == "medium":
        det = "PP-OCRv6_medium_det"
        rec = "PP-OCRv6_medium_rec"
    else:
        det = "PP-OCRv5_mobile_det"
        rec = "PP-OCRv5_mobile_rec"

    with _ocr_lock:
        if key not in _ocr_cache:
            _ocr_cache[key] = PaddleOCR(
                lang=language,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=use_angle,
                enable_mkldnn=False,
                text_detection_model_name=det,
                text_recognition_model_name=rec,
            )
        return _ocr_cache[key]


class PaddleOCRNode(BaseNode):
    type = "paddle-ocr"
    name = "Paddle OCR"
    category = "extraction"
    icon = "\U0001f50d"
    color = "#f59e0b"
    description = "State-of-the-art OCR for printed and handwritten text using PaddleOCR (PP-OCRv6)"
    version = "1.0.0"

    inputs = [
        Port(
            name="image",
            type=PortType.IMAGE,
            label="Image",
            description="Image or document to recognize text from",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Extracted Text",
            description="Combined recognized text from all detected lines",
        ),
        Port(
            name="lines",
            type=PortType.JSON,
            label="Lines",
            description="List of {text, confidence} per detected line",
        ),
        Port(
            name="stats",
            type=PortType.JSON,
            label="Statistics",
            description="Line count and average confidence",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID from /api/documents/upload. Leave empty if image comes from upstream.",
        ),
        ConfigField(
            key="language",
            label="Language",
            type="text",
            required=False,
            default="en",
            description="OCR language code (en, ar, fr, etc.). For multiple: use comma-separated.",
        ),
        ConfigField(
            key="use_angle_cls",
            label="Use Angle Classification",
            type="boolean",
            required=False,
            default=False,
            description="Detect and correct text rotation angle",
        ),
        ConfigField(
            key="model_size",
            label="Model Size",
            type="select",
            required=False,
            default="medium",
            options=["mobile", "medium"],
            description="mobile = fast (PP-OCRv5) | medium = more accurate (PP-OCRv6, recommended)",
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
            language = config.get("language", "en")
            use_angle = bool(config.get("use_angle_cls", False))
            model_size = config.get("model_size", "medium")

            image_input = ctx.get_input("image")
            image_path = ""
            if isinstance(image_input, dict):
                image_path = image_input.get("path") or image_input.get("file_path") or ""
            elif isinstance(image_input, str):
                image_path = image_input

            if not image_path or not image_path.strip():
                file_id = config.get("file_id", "")
                if file_id:
                    file_data = await self._resolve_by_file_id(file_id)
                    if file_data:
                        image_path = file_data.get("path", "")

            if not image_path or not image_path.strip():
                result.fail("No image provided via input port or 'file_id' config")
                return result

            if not Path(image_path).exists():
                result.fail(f"Image not found at path: {image_path}")
                return result

            ocr = _get_paddle_ocr(language, use_angle, model_size)

            ocr_result = ocr.predict(str(image_path))

            lines: list[dict[str, Any]] = []
            for page in ocr_result:
                texts = page.get("rec_texts", []) if isinstance(page, dict) else []
                scores = page.get("rec_scores", []) if isinstance(page, dict) else []
                for text, score in zip(texts, scores):
                    if text and text.strip():
                        lines.append({
                            "text": text.strip(),
                            "confidence": round(float(score), 4),
                        })

            full_text = "\n".join(l["text"] for l in lines)
            avg_conf = round(sum(l["confidence"] for l in lines) / len(lines), 4) if lines else 0.0

            result.succeed({
                "text": full_text,
                "lines": lines,
                "stats": {
                    "total_lines": len(lines),
                    "avg_confidence": avg_conf,
                    "total_chars": len(full_text),
                },
            })

        except Exception as e:
            result.fail(f"Paddle OCR failed: {e}")

        return result

    async def _resolve_by_file_id(self, file_id: str) -> dict[str, Any] | None:
        upload_dir = self._get_upload_dir()
        if not upload_dir.exists():
            return None
        index_path = upload_dir / ".documents-index.json"
        if index_path.exists():
            import json
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
                record = index.get(file_id) if isinstance(index, dict) else None
                if record:
                    file_path = Path(record.get("path", ""))
                    if file_path.exists():
                        return {"file_id": file_id, "path": str(file_path)}
            except (OSError, ValueError):
                pass
        for f in upload_dir.iterdir():
            if f.is_file() and not f.name.startswith(".") and f.stem == file_id:
                return {"file_id": file_id, "path": str(f)}
        return None
