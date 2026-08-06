from __future__ import annotations

import ipaddress
import json
import mimetypes
import os
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

router = APIRouter(prefix="/api/documents", tags=["Documents"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR") or os.getenv("SYMPACT_UPLOAD_DIR") or "data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
INDEX_PATH = UPLOAD_DIR / ".documents-index.json"
MAX_UPLOAD_BYTES = int(os.getenv("SYMPACT_MAX_UPLOAD_MB", "50")) * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp",
    ".docx", ".txt", ".md", ".csv", ".xlsx", ".xlsm",
}


class CloudImportRequest(BaseModel):
    url: HttpUrl
    filename: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_index() -> dict[str, dict]:
    if not INDEX_PATH.exists():
        return {}
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_index(index: dict[str, dict]) -> None:
    temporary_path = INDEX_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(INDEX_PATH)


def _safe_original_name(filename: str | None, fallback: str = "document") -> str:
    cleaned = Path((filename or fallback).replace("\x00", "")).name.strip()
    return cleaned or fallback


def _validate_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"File type '{extension or 'unknown'}' not allowed. Allowed: {allowed}",
        )
    return extension


def _record_to_response(record: dict) -> dict:
    file_id = record["file_id"]
    return {
        **record,
        "download_url": f"/api/documents/{file_id}/download",
    }


def _store_bytes(*, content: bytes, filename: str, mime_type: str | None, source: str, relative_path: str | None = None) -> dict:
    if not content:
        raise HTTPException(status_code=400, detail="The selected file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        max_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File exceeds the {max_mb} MB limit.")

    original_name = _safe_original_name(filename)
    extension = _validate_extension(original_name)
    file_id = str(uuid.uuid4())
    stored_name = f"{file_id}{extension}"
    file_path = UPLOAD_DIR / stored_name
    file_path.write_bytes(content)

    safe_relative_path = None
    if relative_path:
        parts = [part for part in str(relative_path).replace("\\", "/").split("/") if part not in {"", ".", ".."}]
        if parts:
            safe_relative_path = "/".join(parts)

    record = {
        "file_id": file_id,
        "filename": original_name,
        "relative_path": safe_relative_path or original_name,
        "stored_name": stored_name,
        "size_bytes": len(content),
        "mime_type": mime_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream",
        "extension": extension,
        "path": str(file_path),
        "source": source,
        "uploaded_at": _now_iso(),
    }
    index = _load_index()
    index[file_id] = record
    _save_index(index)
    return _record_to_response(record)


def _find_record(file_id: str) -> dict | None:
    index = _load_index()
    record = index.get(file_id)
    if record:
        path = Path(record.get("path", ""))
        if path.exists():
            return record
        index.pop(file_id, None)
        _save_index(index)

    # Backward compatibility with files uploaded by previous versions.
    for candidate in UPLOAD_DIR.iterdir():
        if candidate.is_file() and not candidate.name.startswith(".") and candidate.stem == file_id:
            record = {
                "file_id": file_id,
                "filename": candidate.name,
                "stored_name": candidate.name,
                "size_bytes": candidate.stat().st_size,
                "mime_type": mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
                "extension": candidate.suffix.lower(),
                "path": str(candidate),
                "source": "local",
                "uploaded_at": datetime.fromtimestamp(candidate.stat().st_mtime, timezone.utc).isoformat(),
            }
            index[file_id] = record
            _save_index(index)
            return record
    return None


def _assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Only public HTTP or HTTPS URLs are accepted.")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="The cloud host could not be resolved.") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise HTTPException(status_code=400, detail="Private or local network URLs are not allowed.")


@router.get("")
async def list_documents():
    index = _load_index()

    # Discover older files that are not yet present in the index.
    for candidate in UPLOAD_DIR.iterdir():
        if not candidate.is_file() or candidate.name.startswith("."):
            continue
        if candidate.stem not in index:
            _find_record(candidate.stem)
    index = _load_index()

    existing = [record for record in index.values() if Path(record.get("path", "")).exists()]
    existing.sort(key=lambda item: item.get("uploaded_at", ""), reverse=True)
    return {"documents": [_record_to_response(record) for record in existing], "total": len(existing)}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    original_name = _safe_original_name(file.filename)
    _validate_extension(original_name)
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    return _store_bytes(
        content=content,
        filename=original_name,
        mime_type=file.content_type,
        source="local",
    )


@router.post("/upload/batch")
async def upload_documents(
    files: list[UploadFile] = File(...),
    relative_paths: list[str] | None = Form(default=None),
):
    if not files:
        raise HTTPException(status_code=400, detail="Select at least one file.")

    uploaded: list[dict] = []
    errors: list[dict] = []
    paths = relative_paths or []
    for index, file in enumerate(files):
        relative_path = paths[index] if index < len(paths) else file.filename
        try:
            original_name = _safe_original_name(file.filename)
            _validate_extension(original_name)
            content = await file.read(MAX_UPLOAD_BYTES + 1)
            uploaded.append(_store_bytes(
                content=content,
                filename=original_name,
                mime_type=file.content_type,
                source="local-folder" if relative_path and "/" in relative_path.replace("\\", "/") else "local",
                relative_path=relative_path,
            ))
        except HTTPException as exc:
            errors.append({"filename": file.filename, "relative_path": relative_path, "error": exc.detail})
    return {"documents": uploaded, "errors": errors, "uploaded": len(uploaded), "failed": len(errors)}


@router.post("/import-url")
async def import_document_from_url(request: CloudImportRequest):
    url = str(request.url)
    _assert_public_http_url(url)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                # Validate the final URL too, because the client follows redirects.
                _assert_public_http_url(str(response.url))
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > MAX_UPLOAD_BYTES:
                            raise HTTPException(status_code=413, detail="The remote file exceeds the upload limit.")
                    except ValueError:
                        pass

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="The remote file exceeds the upload limit.")
                    chunks.append(chunk)

                disposition = response.headers.get("content-disposition", "")
                disposition_name = None
                if "filename=" in disposition:
                    disposition_name = disposition.split("filename=", 1)[1].strip().strip('"\'')
                url_name = unquote(Path(urlparse(str(response.url)).path).name)
                filename = _safe_original_name(request.filename or disposition_name or url_name, "cloud-document")
                return _store_bytes(
                    content=b"".join(chunks),
                    filename=filename,
                    mime_type=response.headers.get("content-type", "").split(";", 1)[0] or None,
                    source="cloud-url",
                )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"Unable to download the cloud file: {exc}") from exc


@router.get("/{file_id}")
async def get_document(file_id: str):
    record = _find_record(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    return _record_to_response(record)


@router.get("/{file_id}/download")
async def download_document(file_id: str):
    record = _find_record(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=record["path"],
        media_type=record.get("mime_type") or "application/octet-stream",
        filename=record.get("filename") or Path(record["path"]).name,
    )


@router.delete("/{file_id}")
async def delete_document(file_id: str):
    record = _find_record(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    path = Path(record["path"])
    if path.exists():
        path.unlink()
    index = _load_index()
    index.pop(file_id, None)
    _save_index(index)
    return {"status": "deleted", "file_id": file_id}
