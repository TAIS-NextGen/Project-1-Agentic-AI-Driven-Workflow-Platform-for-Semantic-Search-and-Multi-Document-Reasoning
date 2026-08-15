from __future__ import annotations

import difflib
import html
import json
import os
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any

from backend.nodes.ingestion.document_parser import DocumentParserNode
from backend.sdk import BaseNode, ConfigField, ExecutionContext, NodeResult, Port, PortType


class ComparisonAgentNode(BaseNode):
    """Compare two complete documents and return structured, readable differences."""

    type = "comparison-agent"
    name = "Comparison Agent"
    category = "agents"
    icon = "⚖️"
    color = "#38bdf8"
    description = "Compare two documents and show additions, deletions, and modified content"
    version = "1.0.0"

    inputs = [
        Port(
            name="original_document",
            type=PortType.DOCUMENT,
            label="Original Document",
            description="Reference document used as the comparison baseline",
            required=True,
        ),
        Port(
            name="revised_document",
            type=PortType.DOCUMENT,
            label="Document to Compare",
            description="New or revised document to compare with the original",
            required=True,
        ),
    ]

    outputs = [
        Port(
            name="comparison",
            type=PortType.JSON,
            label="Comparison Result",
            description="Documents, summary, and all structured changes",
        ),
        Port(
            name="summary",
            type=PortType.JSON,
            label="Comparison Summary",
            description="Similarity score and change counters",
        ),
        Port(
            name="diff",
            type=PortType.TEXT,
            label="Unified Diff",
            description="Standard text diff with added and removed lines",
        ),
        Port(
            name="downloads",
            type=PortType.JSON,
            label="Downloadable Reports",
            description="JSON, text diff, HTML comparison, and ZIP bundle",
        ),
        Port(
            name="metadata",
            type=PortType.JSON,
            label="Comparison Metadata",
            description="Parser engines, filenames, and comparison settings",
        ),
    ]

    config_fields = [
        ConfigField(
            key="comparison_level",
            label="Comparison Detail",
            type="select",
            required=False,
            default="line",
            options=["line", "paragraph"],
            description="Compare line by line or paragraph by paragraph.",
        ),
        ConfigField(
            key="ignore_whitespace",
            label="Ignore Spacing Differences",
            type="boolean",
            required=False,
            default=True,
            description="Ignore differences caused only by repeated spaces or line indentation.",
        ),
        ConfigField(
            key="ignore_case",
            label="Ignore Upper/Lower Case",
            type="boolean",
            required=False,
            default=False,
            description="Treat uppercase and lowercase text as equivalent.",
        ),
        ConfigField(
            key="create_downloads",
            label="Create Downloadable Reports",
            type="boolean",
            required=False,
            default=True,
            description="Create JSON, unified diff, HTML, and ZIP reports.",
        ),
    ]

    _SUPPORTED = {".pdf", ".docx", ".xlsx", ".xlsm", ".csv", ".txt", ".md"}

    @staticmethod
    def _storage_dir() -> Path:
        return Path(os.getenv("STORAGE_DIR") or os.getenv("SYMPACT_STORAGE_DIR") or "data/storage")

    @staticmethod
    def _safe_stem(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(value).stem).strip("-._")
        return cleaned or "document"

    @classmethod
    def _resolve_document(cls, value: Any, label: str) -> dict[str, Any]:
        document = DocumentParserNode._candidate_to_file_data(value)
        if not document:
            raise ValueError(f"{label} is missing or does not contain a readable file path")
        path_value = document.get("path") or document.get("file_path")
        path = Path(str(path_value or ""))
        if not path.exists() or not path.is_file():
            raise ValueError(f"{label} file was not found")
        extension = path.suffix.lower()
        if extension not in cls._SUPPORTED:
            raise ValueError(
                f"{label} format '{extension or 'unknown'}' is not supported. "
                f"Supported formats: {', '.join(sorted(cls._SUPPORTED))}"
            )
        document["path"] = str(path)
        document["file_path"] = str(path)
        document.setdefault("filename", path.name)
        document.setdefault("size_bytes", path.stat().st_size)
        document["extension"] = extension
        return document

    @classmethod
    def _parse_document(cls, document: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        path = Path(str(document["path"]))
        extension = path.suffix.lower()

        if extension == ".pdf":
            text, parser_data = DocumentParserNode._parse_pdf(path, preserve_page_breaks=True)
            if not text.strip() and parser_data.get("requires_ocr"):
                raise ValueError(f"{document['filename']} has no searchable text layer. Add OCR before comparison.")
            engine = "pypdf"
        elif extension == ".docx":
            text, parser_data = DocumentParserNode._parse_docx(
                path,
                include_tables=True,
                include_headers_footers=True,
            )
            engine = "python-docx"
        elif extension in {".xlsx", ".xlsm"}:
            text, parser_data = DocumentParserNode._parse_xlsx(
                path,
                include_tables=True,
                sheet_name="",
                max_rows=None,
            )
            engine = "openpyxl"
        elif extension == ".csv":
            text, parser_data = DocumentParserNode._parse_csv(path, include_tables=True, max_rows=None)
            engine = "python-csv"
        else:
            text = DocumentParserNode._read_text_file(path)
            parser_data = {"line_count": len(text.splitlines())}
            engine = "python-text"

        return text, {
            "filename": str(document.get("filename") or path.name),
            "path": str(path),
            "extension": extension,
            "size_bytes": int(document.get("size_bytes") or path.stat().st_size),
            "parser_engine": engine,
            "character_count": len(text),
            "line_count": len(text.splitlines()),
            "parser_data": parser_data,
        }

    @staticmethod
    def _split_units(text: str, level: str) -> list[str]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if level == "paragraph":
            paragraphs = [part.strip("\n") for part in re.split(r"\n\s*\n+", normalized) if part.strip()]
            # Many extracted PDFs and DOCX files contain one logical paragraph per line,
            # without blank separators. Falling back to non-empty lines gives a useful diff.
            if len(paragraphs) <= 1:
                return [line for line in normalized.split("\n") if line.strip()]
            return paragraphs
        return normalized.split("\n")

    @staticmethod
    def _normalise_unit(value: str, *, ignore_whitespace: bool, ignore_case: bool) -> str:
        result = value
        if ignore_whitespace:
            result = re.sub(r"\s+", " ", result).strip()
        if ignore_case:
            result = result.casefold()
        return result

    @staticmethod
    def _word_segments(original: str, revised: str) -> list[dict[str, str]]:
        token_pattern = re.compile(r"\s+|[\w]+|[^\w\s]", flags=re.UNICODE)
        old_tokens = token_pattern.findall(original)
        new_tokens = token_pattern.findall(revised)
        matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
        segments: list[dict[str, str]] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                text = "".join(old_tokens[i1:i2])
                if text:
                    segments.append({"type": "equal", "text": text})
            elif tag == "delete":
                text = "".join(old_tokens[i1:i2])
                if text:
                    segments.append({"type": "removed", "text": text})
            elif tag == "insert":
                text = "".join(new_tokens[j1:j2])
                if text:
                    segments.append({"type": "added", "text": text})
            else:
                removed = "".join(old_tokens[i1:i2])
                added = "".join(new_tokens[j1:j2])
                if removed:
                    segments.append({"type": "removed", "text": removed})
                if added:
                    segments.append({"type": "added", "text": added})
        return segments

    @classmethod
    def _compare(
        cls,
        original_text: str,
        revised_text: str,
        *,
        level: str,
        ignore_whitespace: bool,
        ignore_case: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
        original_units = cls._split_units(original_text, level)
        revised_units = cls._split_units(revised_text, level)
        original_normalized = [
            cls._normalise_unit(value, ignore_whitespace=ignore_whitespace, ignore_case=ignore_case)
            for value in original_units
        ]
        revised_normalized = [
            cls._normalise_unit(value, ignore_whitespace=ignore_whitespace, ignore_case=ignore_case)
            for value in revised_units
        ]

        matcher = difflib.SequenceMatcher(None, original_normalized, revised_normalized, autojunk=False)
        changes: list[dict[str, Any]] = []
        unchanged_units = 0
        added_units = 0
        removed_units = 0
        modified_units = 0

        for change_index, (tag, i1, i2, j1, j2) in enumerate(matcher.get_opcodes(), start=1):
            if tag == "equal":
                unchanged_units += i2 - i1
                continue

            original_values = original_units[i1:i2]
            revised_values = revised_units[j1:j2]
            change_type = {
                "insert": "added",
                "delete": "removed",
                "replace": "modified",
            }[tag]
            if tag == "insert":
                added_units += j2 - j1
            elif tag == "delete":
                removed_units += i2 - i1
            else:
                modified_units += max(i2 - i1, j2 - j1)

            original_block = "\n".join(original_values)
            revised_block = "\n".join(revised_values)
            changes.append({
                "id": change_index,
                "type": change_type,
                "original_start": i1 + 1 if i2 > i1 else None,
                "original_end": i2 if i2 > i1 else None,
                "revised_start": j1 + 1 if j2 > j1 else None,
                "revised_end": j2 if j2 > j1 else None,
                "original_text": original_block,
                "revised_text": revised_block,
                "inline_changes": cls._word_segments(original_block, revised_block) if tag == "replace" else [],
            })

        similarity = matcher.ratio()
        unified = "".join(difflib.unified_diff(
            original_text.splitlines(keepends=True),
            revised_text.splitlines(keepends=True),
            fromfile="original",
            tofile="revised",
            lineterm="\n",
        ))
        summary = {
            "identical": not changes,
            "similarity": round(similarity, 6),
            "similarity_percent": round(similarity * 100, 2),
            "change_block_count": len(changes),
            "added_units": added_units,
            "removed_units": removed_units,
            "modified_units": modified_units,
            "unchanged_units": unchanged_units,
            "original_unit_count": len(original_units),
            "revised_unit_count": len(revised_units),
        }
        return changes, summary, unified

    @classmethod
    def _create_downloads(
        cls,
        *,
        original_name: str,
        revised_name: str,
        comparison: dict[str, Any],
        unified_diff: str,
        original_text: str,
        revised_text: str,
    ) -> dict[str, dict[str, Any]]:
        output_root = cls._storage_dir() / "comparison_outputs"
        output_root.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex[:8]
        base = f"{cls._safe_stem(original_name)}-vs-{cls._safe_stem(revised_name)}-{token}"
        json_path = output_root / f"{base}.json"
        diff_path = output_root / f"{base}.diff.txt"
        html_path = output_root / f"{base}.html"
        zip_path = output_root / f"{base}.zip"

        json_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        diff_path.write_text(unified_diff or "The documents are identical.\n", encoding="utf-8")

        html_report = difflib.HtmlDiff(tabsize=4, wrapcolumn=120).make_file(
            original_text.splitlines(),
            revised_text.splitlines(),
            fromdesc=html.escape(original_name),
            todesc=html.escape(revised_name),
            context=True,
            numlines=3,
            charset="utf-8",
        )
        html_path.write_text(html_report, encoding="utf-8")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(json_path, arcname=json_path.name)
            archive.write(diff_path, arcname=diff_path.name)
            archive.write(html_path, arcname=html_path.name)

        def descriptor(path: Path, mime_type: str) -> dict[str, Any]:
            relative = path.relative_to(cls._storage_dir()).as_posix()
            return {
                "filename": path.name,
                "path": str(path),
                "download_url": f"/data/storage/{relative}",
                "mime_type": mime_type,
                "size_bytes": path.stat().st_size,
            }

        return {
            "json": descriptor(json_path, "application/json"),
            "diff": descriptor(diff_path, "text/plain; charset=utf-8"),
            "html": descriptor(html_path, "text/html; charset=utf-8"),
            "bundle": descriptor(zip_path, "application/zip"),
        }

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            original_document = self._resolve_document(ctx.get_input("original_document"), "Original document")
            revised_document = self._resolve_document(ctx.get_input("revised_document"), "Document to compare")

            original_text, original_metadata = self._parse_document(original_document)
            revised_text, revised_metadata = self._parse_document(revised_document)

            level = str(config.get("comparison_level", "line")).strip().lower()
            if level not in {"line", "paragraph"}:
                level = "line"
            ignore_whitespace = bool(config.get("ignore_whitespace", True))
            ignore_case = bool(config.get("ignore_case", False))

            changes, summary, unified_diff = self._compare(
                original_text,
                revised_text,
                level=level,
                ignore_whitespace=ignore_whitespace,
                ignore_case=ignore_case,
            )
            comparison = {
                "original": original_metadata,
                "revised": revised_metadata,
                "summary": summary,
                "changes": changes,
            }
            metadata = {
                "engine": "python-difflib-sequence-matcher",
                "comparison_level": level,
                "ignore_whitespace": ignore_whitespace,
                "ignore_case": ignore_case,
                "original_filename": original_metadata["filename"],
                "revised_filename": revised_metadata["filename"],
                "original_parser_engine": original_metadata["parser_engine"],
                "revised_parser_engine": revised_metadata["parser_engine"],
            }

            downloads: dict[str, dict[str, Any]] = {}
            if bool(config.get("create_downloads", True)):
                downloads = self._create_downloads(
                    original_name=original_metadata["filename"],
                    revised_name=revised_metadata["filename"],
                    comparison={**comparison, "metadata": metadata},
                    unified_diff=unified_diff,
                    original_text=original_text,
                    revised_text=revised_text,
                )

            result.succeed({
                "comparison": comparison,
                "summary": summary,
                "diff": unified_diff,
                "downloads": downloads,
                "metadata": metadata,
            })
        except ImportError as exc:
            result.fail(
                f"Document comparison dependency missing: {exc}. "
                "Install pypdf, python-docx, and openpyxl."
            )
        except Exception as exc:
            result.fail(str(exc))

        return result
