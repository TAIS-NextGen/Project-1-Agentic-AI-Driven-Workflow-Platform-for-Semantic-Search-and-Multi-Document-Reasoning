from __future__ import annotations

import mimetypes
import os
import uuid
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
from backend.services.storage import StorageService


class DocumentUploadNode(BaseNode):
    type = "document-upload"
    name = "Document Upload"
    category = "ingestion"
    icon = "📄"
    color = "#3b82f6"
    description = "Upload and ingest documents into the workflow"
    version = "1.0.0"

    inputs = [
        Port(
            name="file",
            type=PortType.DOCUMENT,
            label="File",
            description="Incoming file reference from upstream node",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="document",
            type=PortType.DOCUMENT,
            label="Document",
            description="Document reference with metadata",
        ),
        Port(
            name="file_path",
            type=PortType.TEXT,
            label="File Path",
            description="Absolute path to the stored file on disk",
        ),
        Port(
            name="file_name",
            type=PortType.TEXT,
            label="File Name",
            description="Original filename",
        ),
        Port(
            name="mime_type",
            type=PortType.TEXT,
            label="MIME Type",
            description="Detected MIME type of the file",
        ),
        Port(
            name="size_bytes",
            type=PortType.JSON,
            label="Size (bytes)",
            description="File size in bytes",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID from /api/documents/upload. If empty, expects file from upstream input.",
        ),
        ConfigField(
            key="allowed_extensions",
            label="Allowed Extensions",
            type="tags",
            required=False,
            default=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".docx", ".txt", ".csv", ".xlsx"],
            description="Comma-separated list of accepted file extensions",
        ),
        ConfigField(
            key="max_file_size_mb",
            label="Max File Size (MB)",
            type="number",
            required=False,
            default=50,
            description="Maximum allowed file size in megabytes",
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
            allowed_exts: list[str] = config.get("allowed_extensions", [])
            max_bytes = int(config.get("max_file_size_mb", 50)) * 1024 * 1024

            file_data: dict[str, Any] | None = ctx.get_input("file")

            if not file_data:
                file_id = config.get("file_id", "")
                if not file_id:
                    result.fail("No file provided via input port or 'file_id' config")
                    return result
                file_data = await self._resolve_by_file_id(file_id)
                if not file_data:
                    result.fail(f"File with ID '{file_id}' not found in upload directory")
                    return result

            file_path = Path(file_data["path"])
            original_name = file_data.get("filename", file_path.name)
            size_bytes = file_data.get("size_bytes", file_path.stat().st_size)

            ext = file_path.suffix.lower()
            if ext not in allowed_exts:
                result.fail(
                    f"File extension '{ext}' not allowed. Allowed: {allowed_exts}"
                )
                return result

            if size_bytes > max_bytes:
                result.fail(
                    f"File size {size_bytes} bytes exceeds maximum of {max_bytes} bytes"
                )
                return result

            mime = file_data.get("mime_type") or mimetypes.guess_type(original_name)[0]
            mime_type = mime or "application/octet-stream"

            storage = StorageService()
            stored_name = f"documents/{uuid.uuid4().hex}{ext}"
            stored_path = await storage.save(stored_name, file_path.read_bytes())

            document_id = str(uuid.uuid4())

            document = {
                "id": document_id,
                "filename": original_name,
                "file_path": stored_path,
                "path": stored_path,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "extension": ext,
            }

            result.succeed({
                "document": document,
                "file_path": str(stored_path),
                "file_name": original_name,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
            })

        except Exception as e:
            result.fail(str(e))

        return result

    async def _resolve_by_file_id(self, file_id: str) -> dict[str, Any] | None:
        upload_dir = self._get_upload_dir()
        if not upload_dir.exists():
            return None
        for f in upload_dir.iterdir():
            if f.stem == file_id:
                return {
                    "file_id": file_id,
                    "filename": f.name,
                    "path": str(f),
                    "size_bytes": f.stat().st_size,
                }
        return None
