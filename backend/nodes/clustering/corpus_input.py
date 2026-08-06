from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Any

from backend.sdk import BaseNode, ConfigField, ExecutionContext, NodeResult, Port, PortType


class CorpusInputNode(BaseNode):
    type = "corpus-input"
    name = "Corpus Input"
    category = "ingestion"
    icon = "📁"
    color = "#0ea5e9"
    description = "Import a folder containing multiple documents as one corpus"
    version = "1.0.0"

    inputs: list[Port] = []
    outputs = [
        Port(
            name="corpus",
            type=PortType.CORPUS,
            label="Document Corpus",
            description="Folder metadata and all selected document references",
        ),
        Port(
            name="documents",
            type=PortType.DOCUMENT_COLLECTION,
            label="Documents",
            description="Selected document references",
        ),
        Port(
            name="metadata",
            type=PortType.JSON,
            label="Corpus Metadata",
            description="Folder name, file count, and supported-file statistics",
        ),
    ]

    config_fields = [
        ConfigField(
            key="folder_name",
            label="Folder Name",
            type="text",
            default="",
            description="Name of the folder selected in the browser.",
        ),
        ConfigField(
            key="file_ids",
            label="Uploaded File IDs",
            type="json",
            default=[],
            description="Files uploaded by the folder picker.",
        ),
        ConfigField(
            key="documents",
            label="Document Records",
            type="json",
            default=[],
            description="Stored document descriptors, including relative folder paths.",
        ),
    ]

    @staticmethod
    def _upload_dir() -> Path:
        return Path(os.getenv("UPLOAD_DIR") or os.getenv("SYMPACT_UPLOAD_DIR") or "data/uploads")

    @classmethod
    def _load_index(cls) -> dict[str, dict[str, Any]]:
        index_path = cls._upload_dir() / ".documents-index.json"
        if not index_path.exists():
            return {}
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _normalise_document(record: Any) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None
        path_value = record.get("path") or record.get("file_path")
        if not isinstance(path_value, str) or not path_value.strip():
            return None
        path = Path(path_value)
        if not path.exists() or not path.is_file():
            return None
        filename = str(record.get("filename") or path.name)
        return {
            "file_id": record.get("file_id"),
            "filename": filename,
            "relative_path": str(record.get("relative_path") or filename),
            "path": str(path),
            "file_path": str(path),
            "mime_type": record.get("mime_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            "extension": str(record.get("extension") or path.suffix.lower()),
            "size_bytes": int(record.get("size_bytes") or path.stat().st_size),
        }

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            configured_documents = config.get("documents")
            records: list[dict[str, Any]] = []

            if isinstance(configured_documents, list):
                records.extend(item for item in configured_documents if isinstance(item, dict))

            known_ids = {
                str(record.get("file_id"))
                for record in records
                if record.get("file_id")
            }
            file_ids = config.get("file_ids")
            if isinstance(file_ids, list):
                index = self._load_index()
                for file_id in file_ids:
                    key = str(file_id)
                    if key in known_ids:
                        continue
                    record = index.get(key)
                    if isinstance(record, dict):
                        records.append({**record, "file_id": key})

            documents: list[dict[str, Any]] = []
            missing: list[str] = []
            for record in records:
                normalised = self._normalise_document(record)
                if normalised:
                    documents.append(normalised)
                else:
                    missing.append(str(record.get("filename") or record.get("file_id") or "unknown"))

            # De-duplicate by file ID when available, otherwise by physical path.
            deduplicated: list[dict[str, Any]] = []
            seen: set[str] = set()
            for document in documents:
                marker = str(document.get("file_id") or document.get("path"))
                if marker in seen:
                    continue
                seen.add(marker)
                deduplicated.append(document)
            documents = deduplicated

            if not documents:
                result.fail("No folder documents are available. Select a folder in the Corpus Input node first.")
                return result

            folder_name = str(config.get("folder_name") or "Document corpus").strip() or "Document corpus"
            corpus = {
                "name": folder_name,
                "documents": documents,
                "document_count": len(documents),
            }
            metadata = {
                "folder_name": folder_name,
                "document_count": len(documents),
                "total_size_bytes": sum(int(document.get("size_bytes", 0)) for document in documents),
                "extensions": sorted({str(document.get("extension") or "") for document in documents}),
                "missing_files": missing,
            }
            result.succeed({"corpus": corpus, "documents": documents, "metadata": metadata})
        except Exception as exc:
            result.fail(str(exc))

        return result
