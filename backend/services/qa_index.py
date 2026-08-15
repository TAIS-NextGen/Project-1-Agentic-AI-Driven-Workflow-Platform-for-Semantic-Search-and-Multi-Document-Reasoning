from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from backend.settings import settings
from backend.services.embedding import EmbeddingService
from backend.services.normalization import TextCleanerService

# In-memory persistent index (module-level singleton). Survives between API
# requests within a backend process; cleared on restart.
_index: dict[str, Any] = {"documents": [], "entries": []}
_index_lock = threading.Lock()

# On-disk persistence path: the extracted text + vectors are saved here after
# indexing so that future backend sessions can load them without re-running OCR.
INDEX_PATH = Path(settings.storage_dir) / "qa_index.json"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif", ".webp"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".tsv"}


def _resolve_file(file_id: str) -> dict[str, Any] | None:
    upload_dir = Path(settings.upload_dir)
    if not upload_dir.exists():
        return None
    index_path = upload_dir / ".documents-index.json"
    if index_path.exists():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            rec = data.get(file_id) if isinstance(data, dict) else None
            if rec:
                p = Path(rec.get("path", ""))
                if p.exists():
                    return {
                        "file_id": file_id,
                        "filename": rec.get("filename", p.name),
                        "path": str(p),
                        "extension": p.suffix.lower(),
                        "mime_type": rec.get("mime_type", ""),
                    }
        except (OSError, json.JSONDecodeError):
            pass
    for f in upload_dir.iterdir():
        if f.is_file() and not f.name.startswith(".") and f.stem == file_id:
            return {"file_id": file_id, "filename": f.name, "path": str(f), "extension": f.suffix.lower()}
    return None


def _extract_text_from_docx(path: str) -> str:
    try:
        import docx

        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs if p.text.strip())
    except Exception:
        return ""


def _extract_text_from_pdf(path: str) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


def _extract_text_via_ocr(path: str) -> str:
    from backend.nodes.extraction.paddle_ocr import _get_paddle_ocr

    ocr = _get_paddle_ocr("en", False, "medium")
    result = ocr.predict(path)
    lines: list[str] = []
    for page in result:
        for t in page.get("rec_texts", []) if isinstance(page, dict) else []:
            if t and t.strip():
                lines.append(t.strip())
    return "\n".join(lines)


def _extract_text(file_data: dict[str, Any]) -> tuple[str, str]:
    """Route a document to the right text extractor based on its extension.
    Returns (text, method) where method is one of ocr/parser/docx/pdf/text."""
    ext = file_data.get("extension", "")
    path = file_data["path"]

    if ext == ".docx":
        text = _extract_text_from_docx(path)
        if text.strip():
            return text, "docx"
    if ext == ".pdf":
        text = _extract_text_from_pdf(path)
        if text.strip():
            return text, "pdf"
    if ext in TEXT_EXTENSIONS:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            if text.strip():
                return text, "text"
        except Exception:
            pass

    # Fallback (and images): OCR
    text = _extract_text_via_ocr(path)
    return text, "ocr"


def _split_text(text: str, chunk_size: int = 512, overlap: int = 100) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


class QAIndexService:
    def __init__(self, embedding_model: str = "nomic-embed-text"):
        self.embedding_model = embedding_model

    async def index_documents(self, file_ids: list[str]) -> dict[str, Any]:
        cleaner = TextCleanerService()
        embedder = EmbeddingService(self.embedding_model)

        documents: list[dict[str, Any]] = []
        entries: list[dict[str, Any]] = []
        methods: dict[str, int] = {}

        for fid in file_ids:
            fd = _resolve_file(str(fid))
            if not fd:
                continue
            raw_text, method = _extract_text(fd)
            if not raw_text.strip():
                continue
            methods[method] = methods.get(method, 0) + 1

            cleaned = cleaner.clean(raw_text)["cleaned_text"]
            chunks = _split_text(cleaned)
            if not chunks:
                continue

            emb_result = await embedder.embed(chunks)
            vectors = [e["vector"] for e in emb_result["embeddings"]]
            for chunk, vec in zip(chunks, vectors):
                entries.append({
                    "doc_id": fid,
                    "filename": fd.get("filename", ""),
                    "chunk_text": chunk,
                    "vector": vec,
                })
            documents.append({
                "file_id": fid,
                "filename": fd.get("filename", ""),
                "extension": fd.get("extension", ""),
                "method": method,
                "chunks": len(chunks),
            })

        with _index_lock:
            _index["documents"] = documents
            _index["entries"] = entries

        if documents:
            self.save()

        return {
            "indexed_documents": len(documents),
            "total_chunks": len(entries),
            "extraction_methods": methods,
        }

    async def query(self, question: str, top_k: int = 5) -> list[dict[str, Any]]:
        embedder = EmbeddingService(self.embedding_model)
        qv = (await embedder.embed([question]))["embeddings"][0]["vector"]

        with _index_lock:
            entries = list(_index["entries"])
        if not entries:
            return []

        scored = []
        for e in entries:
            score = self._cosine(qv, e["vector"])
            scored.append({
                "chunk_text": e["chunk_text"],
                "filename": e["filename"],
                "doc_id": e["doc_id"],
                "score": round(score, 4),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def get_stats(self) -> dict[str, Any]:
        with _index_lock:
            return {"documents": len(_index["documents"]), "chunks": len(_index["entries"])}

    def import_entries(self, entries: list[dict[str, Any]], filename: str = "") -> None:
        """Import pre-computed entries (e.g. produced by the vector-store node)
        into the persistent index, so the qa-chat node can query them."""
        normalized: list[dict[str, Any]] = []
        for e in entries:
            normalized.append({
                "doc_id": str(e.get("chunk_id", e.get("doc_id", ""))),
                "filename": filename or e.get("filename", ""),
                "chunk_text": e.get("chunk_text", ""),
                "vector": e.get("vector", []),
            })
        with _index_lock:
            _index["entries"] = normalized
            if filename:
                _index["documents"] = [{
                    "file_id": filename,
                    "filename": filename,
                    "chunks": len(normalized),
                }]
            else:
                _index["documents"] = []
        if normalized:
            self.save()

    def save(self) -> None:
        """Persist the current index (documents + vectors) to disk."""
        with _index_lock:
            payload = {"documents": _index["documents"], "entries": _index["entries"]}
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls) -> bool:
        """Restore the index from disk. Returns True if a saved index was found."""
        if not INDEX_PATH.exists():
            return False
        try:
            payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            with _index_lock:
                _index["documents"] = payload.get("documents", [])
                _index["entries"] = payload.get("entries", [])
            return True
        except (OSError, json.JSONDecodeError):
            return False
