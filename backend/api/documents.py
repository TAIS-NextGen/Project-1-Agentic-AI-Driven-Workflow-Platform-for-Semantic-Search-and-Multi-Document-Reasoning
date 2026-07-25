import os
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter(prefix="/api/documents", tags=["Documents"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".docx", ".txt", ".csv", ".xlsx"}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {ALLOWED_EXTENSIONS}",
        )

    file_id = str(uuid.uuid4())
    safe_name = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / safe_name

    content = await file.read()
    file_path.write_bytes(content)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size_bytes": len(content),
        "mime_type": file.content_type or "application/octet-stream",
        "path": str(file_path),
    }


@router.get("/{file_id}")
async def get_document(file_id: str):
    for f in UPLOAD_DIR.iterdir():
        if f.stem == file_id:
            return {
                "file_id": file_id,
                "filename": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
            }
    raise HTTPException(status_code=404, detail="File not found")


@router.delete("/{file_id}")
async def delete_document(file_id: str):
    for f in UPLOAD_DIR.iterdir():
        if f.stem == file_id:
            f.unlink()
            return {"status": "deleted", "file_id": file_id}
    raise HTTPException(status_code=404, detail="File not found")
