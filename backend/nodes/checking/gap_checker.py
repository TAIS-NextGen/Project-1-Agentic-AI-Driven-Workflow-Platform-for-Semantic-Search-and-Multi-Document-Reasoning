from __future__ import annotations

import json as json_lib
import os
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
from backend.services.gap_checker import GapCheckerService


class GapCheckerNode(BaseNode):
    type = "gap-checker"
    name = "Gap Checker"
    category = "checking"
    icon = "\U0001f50e"
    color = "#ef4444"
    description = "Verifier les champs manquants dans un document par rapport a une checklist de reference"
    version = "1.0.0"

    inputs = [
        Port(
            name="document",
            type=PortType.DOCUMENT,
            label="Document",
            description="Document a analyser (PDF, image, texte)",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="report",
            type=PortType.JSON,
            label="Gap Report",
            description="Analyse detaillee champ par champ avec statut de chaque champ",
        ),
        Port(
            name="score",
            type=PortType.JSON,
            label="Completeness Score",
            description="Score de completude (pourcentage, champs critiques manquants, seuil depasse)",
        ),
        Port(
            name="missing",
            type=PortType.JSON,
            label="Missing Fields",
            description="Liste des champs critiques manquants uniquement",
        ),
    ]

    config_fields = [
        ConfigField(
            key="file_id",
            label="File ID",
            type="text",
            required=False,
            default="",
            description="File ID from /api/documents/upload. If empty, expects document from upstream input.",
        ),
        ConfigField(
            key="template",
            label="Checklist Template",
            type="text",
            required=False,
            default="generic",
            description="Template name: generic, invoice_fr, claim_dossier",
        ),
        ConfigField(
            key="strictness_threshold",
            label="Strictness Threshold",
            type="number",
            required=False,
            default=0.85,
            description="Minimum completeness percentage to pass (0.0 - 1.0)",
        ),
        ConfigField(
            key="evaluation_mode",
            label="Evaluation Mode",
            type="select",
            required=False,
            default="both",
            options=["deterministic_only", "semantic", "both"],
            description="'deterministic_only': regex only, no LLM. 'semantic': LLM only. 'both': regex + LLM for unfound fields.",
        ),
        ConfigField(
            key="custom_checklist",
            label="Custom Checklist",
            type="json",
            required=False,
            default="[]",
            description="Inline JSON checklist array (used instead of template if non-empty)",
        ),
        ConfigField(
            key="allowed_extensions",
            label="Allowed Extensions",
            type="tags",
            required=False,
            default=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".txt"],
            description="Accepted file extensions",
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
            template = config.get("template", "generic")
            threshold = float(config.get("strictness_threshold", 0.85))
            mode = config.get("evaluation_mode", "both")

            file_data: dict[str, Any] | None = ctx.get_input("document")

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
            if not file_path.exists():
                result.fail(f"File not found at path: {file_path}")
                return result

            original_name = file_data.get("filename", file_path.name)
            ext = file_path.suffix.lower()
            if ext not in allowed_exts:
                result.fail(f"File extension '{ext}' not allowed. Allowed: {allowed_exts}")
                return result

            text = await self._extract_text(file_path, ext)

            if not text or not text.strip():
                result.fail("Could not extract any text from the document")
                return result

            service = GapCheckerService()

            custom_raw = config.get("custom_checklist", "[]")
            if isinstance(custom_raw, str) and custom_raw.strip() and custom_raw.strip() != "[]":
                checklist = service._parse_custom_checklist(custom_raw)
            else:
                checklist = service.load_checklist(template)

            gap_result = await service.check(
                text=text,
                checklist=checklist,
                mode=mode,
                threshold=threshold,
            )

            result.succeed({
                "report": {
                    "fields": gap_result["fields"],
                    "has_critical_gaps": gap_result["has_critical_gaps"],
                    "filename": original_name,
                },
                "score": gap_result["score"],
                "missing": gap_result["missing"],
            })

        except Exception as e:
            result.fail(str(e))

        return result

    async def _extract_text(self, file_path: Path, ext: str) -> str:
        if ext == ".txt":
            return file_path.read_text(encoding="utf-8", errors="replace")
        from backend.services.ocr import OCRService

        ocr = OCRService()
        ocr_result = await ocr.extract_text(str(file_path))
        return ocr_result.get("text", "")

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
