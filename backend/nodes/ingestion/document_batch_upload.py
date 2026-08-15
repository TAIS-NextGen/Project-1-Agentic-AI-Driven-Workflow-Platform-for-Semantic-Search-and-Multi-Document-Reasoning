from __future__ import annotations

import json
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


class DocumentBatchUploadNode(BaseNode):
    type = "document-batch-upload"
    name = "Document Batch Upload"
    category = "ingestion"
    icon = "📦"
    color = "#3b82f6"
    description = "Upload and ingest multiple documents into the workflow at once"
    version = "1.0.0"

    inputs = [
        Port(
            name="documents",
            type=PortType.DOCUMENT_COLLECTION,
            label="Documents",
            description="Incoming document collection from upstream node",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="documents",
            type=PortType.DOCUMENT_COLLECTION,
            label="Documents",
            description="Array of document references with metadata for each file",
        ),
        Port(
            name="file_paths",
            type=PortType.JSON,
            label="File Paths",
            description="Array of absolute paths to stored files",
        ),
        Port(
            name="file_names",
            type=PortType.JSON,
            label="File Names",
            description="Array of original filenames",
        ),
        Port(
            name="document_count",
            type=PortType.JSON,
            label="Document Count",
            description="Number of documents processed",
        ),
        Port(
            name="file_ids",
            type=PortType.JSON,
            label="File IDs",
            description="Original library file IDs (for downstream indexing)",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_ids",
            label="File IDs",
            type="tags",
            required=False,
            default=[],
            description="List of file IDs from /api/documents/upload. If empty, expects documents from upstream input.",
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

            file_list: list[dict[str, Any]] = ctx.get_input("documents") or []
            resolved_file_ids: list[str] = []

            if not file_list:
                file_ids = config.get("file_ids", [])
                if isinstance(file_ids, str):
                    file_ids = [fid.strip() for fid in file_ids.split(",") if fid.strip()]
                if not file_ids:
                    result.fail("No documents provided via input port or 'file_ids' config")
                    return result

                file_list = []
                for file_id in file_ids:
                    file_data = await self._resolve_by_file_id(str(file_id))
                    if not file_data:
                        result.fail(f"File with ID '{file_id}' not found in upload directory")
                        return result
                    resolved_file_ids.append(str(file_id))
                    file_list.append(file_data)

            documents = []
            file_paths = []
            file_names = []

            for file_data in file_list:
                file_path = Path(file_data["path"])
                original_name = file_data.get("filename", file_path.name)
                size_bytes = file_data.get("size_bytes", file_path.stat().st_size)

                ext = file_path.suffix.lower()
                if ext not in allowed_exts:
                    result.fail(f"File extension '{ext}' not allowed for '{original_name}'. Allowed: {allowed_exts}")
                    return result

                if size_bytes > max_bytes:
                    result.fail(
                        f"File '{original_name}' size {size_bytes} bytes exceeds maximum of {max_bytes} bytes"
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
                documents.append(document)
                file_paths.append(str(stored_path))
                file_names.append(original_name)

            result.succeed({
                "documents": documents,
                "file_paths": file_paths,
                "file_names": file_names,
                "document_count": len(documents),
                "file_ids": resolved_file_ids,
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
