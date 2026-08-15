from __future__ import annotations

import ipaddress
import os
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from backend.nodes.ingestion.document_parser import DocumentParserNode
from backend.sdk import BaseNode, ConfigField, ExecutionContext, NodeResult, Port, PortType
from backend.services.conversion import FileConversionService

try:  # PyMuPDF >= 1.24
    import pymupdf
except ImportError:  # pragma: no cover - compatibility with older package name
    import fitz as pymupdf  # type: ignore


@dataclass(frozen=True)
class _Detection:
    entity_type: str
    start: int
    end: int
    priority: int


@dataclass(frozen=True)
class _MappedWord:
    start: int
    end: int
    block: int
    line: int
    rect: Any


class MaskerNode(BaseNode):
    """Permanently redact sensitive information from a PDF.

    The node accepts a PDF document directly, or a text-producing node whose
    upstream lineage still contains the source document. It always creates a new
    PDF: the original input file is never modified.
    """

    type = "masker"
    name = "Masker"
    category = "preprocessing"
    icon = "🛡️"
    color = "#ef4444"
    description = "Mask sensitive data in a PDF while preserving the document layout"
    version = "1.0.0"

    inputs = [
        Port(
            name="document",
            type=PortType.DOCUMENT,
            label="Document",
            description="PDF or convertible document to anonymize",
            required=False,
        ),
        Port(
            name="text",
            type=PortType.TEXT,
            label="Document Text",
            description="Text produced from the document; the source PDF is recovered from upstream lineage",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="document",
            type=PortType.DOCUMENT,
            label="Masked PDF",
            description="New PDF with sensitive values permanently removed",
        ),
        Port(
            name="report",
            type=PortType.JSON,
            label="Masking Report",
            description="Counts by sensitive-data category without exposing the detected values",
        ),
        Port(
            name="metadata",
            type=PortType.JSON,
            label="Metadata",
            description="Source, output, page and redaction information",
        ),
    ]

    config_fields = [
        ConfigField(
            key="mask_emails",
            label="Emails",
            type="boolean",
            default=True,
            description="Mask email addresses.",
        ),
        ConfigField(
            key="mask_phones",
            label="Phone Numbers",
            type="boolean",
            default=True,
            description="Mask local and international phone numbers.",
        ),
        ConfigField(
            key="mask_ids",
            label="Identifiers",
            type="boolean",
            default=True,
            description="Mask labelled identifiers such as ID, CIN, passport, SSN and matricule values.",
        ),
        ConfigField(
            key="mask_addresses",
            label="Postal Addresses",
            type="boolean",
            default=True,
            description="Mask common postal-address expressions.",
        ),
        ConfigField(
            key="mask_financial",
            label="Financial Data",
            type="boolean",
            default=True,
            description="Mask IBANs and payment-card numbers.",
        ),
        ConfigField(
            key="mask_ip_addresses",
            label="IP Addresses",
            type="boolean",
            default=True,
            description="Mask IPv4 addresses.",
        ),
        ConfigField(
            key="mask_style",
            label="Mask Style",
            type="select",
            default="black",
            options=["black", "white"],
            description="Draw black or white permanent redaction boxes.",
        ),
    ]

    _EMAIL_RE = re.compile(
        r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
        re.IGNORECASE,
    )
    _IBAN_RE = re.compile(
        r"(?<![A-Z0-9])[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]){11,30}(?![A-Z0-9])",
        re.IGNORECASE,
    )
    _CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
    _PHONE_RE = re.compile(
        r"(?<![\w/])(?:\+|00)?\d{1,3}"
        r"(?:[ .-]?\(?\d{1,4}\)?){2,5}[ .-]?\d{2,4}(?![\w/])"
    )
    _ID_RE = re.compile(
        r"(?<!\w)(?:"
        r"CIN|ID|IDENTIFIER|IDENTIFIANT|PASSPORT|PASSEPORT|MATRICULE|SSN|NIR|"
        r"N[°O]?\s*(?:CARTE|IDENTIT[ÉE]|PASSEPORT)|"
        r"رقم\s*(?:الهوية|البطاقة|بطاقة\s*التعريف|جواز\s*السفر)|"
        r"بطاقة\s*التعريف"
        r")\s*[:#№-]?\s*[A-Z0-9][A-Z0-9./_-]{4,30}(?!\w)",
        re.IGNORECASE,
    )
    _LATIN_ADDRESS_RE = re.compile(
        r"(?<!\w)\d{1,5}(?:\s*(?:bis|ter))?\s+"
        r"(?:[A-ZÀ-ÖØ-öø-ÿ0-9'’.-]+\s+){0,7}"
        r"(?:rue|avenue|av\.?|boulevard|bd\.?|route|chemin|impasse|place|quai|"
        r"street|st\.?|road|rd\.?|lane|drive|square)"
        r"(?:\s+[A-ZÀ-ÖØ-öø-ÿ0-9'’.-]+){0,8}(?!\w)",
        re.IGNORECASE,
    )
    _ARABIC_ADDRESS_RE = re.compile(
        r"(?<!\w)(?:\d{1,5}\s+)?(?:شارع|نهج|طريق|حي|إقامة|اقامة)"
        r"(?:\s+[\u0600-\u06FF0-9٠-٩-]+){1,7}(?!\w)",
        re.IGNORECASE,
    )
    _IPV4_RE = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")

    @staticmethod
    def _storage_dir() -> Path:
        return Path(os.getenv("STORAGE_DIR") or os.getenv("SYMPACT_STORAGE_DIR") or "data/storage")

    @staticmethod
    def _safe_stem(filename: str) -> str:
        stem = Path(filename).stem
        stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip(" .")
        return stem or "document"

    @staticmethod
    def _digits(value: str) -> str:
        return "".join(character for character in value if character.isdigit())

    @classmethod
    def _is_card_number(cls, value: str) -> bool:
        digits = cls._digits(value)
        if not 13 <= len(digits) <= 19:
            return False
        checksum = 0
        parity = len(digits) % 2
        for index, character in enumerate(digits):
            number = int(character)
            if index % 2 == parity:
                number *= 2
                if number > 9:
                    number -= 9
            checksum += number
        return checksum % 10 == 0

    @classmethod
    def _is_phone_number(cls, value: str) -> bool:
        digits = cls._digits(value)
        return 7 <= len(digits) <= 15

    @staticmethod
    def _is_ipv4(value: str) -> bool:
        try:
            ipaddress.IPv4Address(value)
            return True
        except ipaddress.AddressValueError:
            return False

    @classmethod
    def _enabled_entity_types(cls, config: dict[str, Any]) -> set[str]:
        mapping = {
            "EMAIL": "mask_emails",
            "PHONE": "mask_phones",
            "ID": "mask_ids",
            "ADDRESS": "mask_addresses",
            "FINANCIAL": "mask_financial",
            "IP_ADDRESS": "mask_ip_addresses",
        }
        return {
            entity_type
            for entity_type, config_key in mapping.items()
            if bool(config.get(config_key, True))
        }

    @classmethod
    def _raw_detections(cls, text: str, enabled: set[str]) -> Iterable[_Detection]:
        if "FINANCIAL" in enabled:
            for match in cls._IBAN_RE.finditer(text):
                yield _Detection("FINANCIAL", match.start(), match.end(), 100)
            for match in cls._CARD_RE.finditer(text):
                if cls._is_card_number(match.group(0)):
                    yield _Detection("FINANCIAL", match.start(), match.end(), 95)

        if "EMAIL" in enabled:
            for match in cls._EMAIL_RE.finditer(text):
                yield _Detection("EMAIL", match.start(), match.end(), 90)

        if "ID" in enabled:
            for match in cls._ID_RE.finditer(text):
                yield _Detection("ID", match.start(), match.end(), 85)

        if "PHONE" in enabled:
            for match in cls._PHONE_RE.finditer(text):
                if cls._is_phone_number(match.group(0)):
                    yield _Detection("PHONE", match.start(), match.end(), 70)

        if "ADDRESS" in enabled:
            for expression in (cls._LATIN_ADDRESS_RE, cls._ARABIC_ADDRESS_RE):
                for match in expression.finditer(text):
                    yield _Detection("ADDRESS", match.start(), match.end(), 60)

        if "IP_ADDRESS" in enabled:
            for match in cls._IPV4_RE.finditer(text):
                if cls._is_ipv4(match.group(0)):
                    yield _Detection("IP_ADDRESS", match.start(), match.end(), 88)

    @classmethod
    def detect_sensitive_spans(cls, text: str, enabled: set[str]) -> list[_Detection]:
        """Return non-overlapping sensitive spans without exposing values."""
        candidates = sorted(
            cls._raw_detections(text, enabled),
            key=lambda item: (item.start, -item.priority, -(item.end - item.start)),
        )
        accepted: list[_Detection] = []
        for candidate in candidates:
            overlaps = any(
                candidate.start < existing.end and existing.start < candidate.end
                for existing in accepted
            )
            if not overlaps:
                accepted.append(candidate)
        return accepted

    @staticmethod
    def _page_text_map(page: Any) -> tuple[str, list[_MappedWord]]:
        words = page.get_text("words", sort=True)
        parts: list[str] = []
        mapped: list[_MappedWord] = []
        cursor = 0
        previous_line: tuple[int, int] | None = None

        for word in words:
            x0, y0, x1, y1, value, block, line, _word_number = word[:8]
            value = str(value)
            if not value:
                continue
            current_line = (int(block), int(line))
            if parts:
                separator = "\n" if previous_line != current_line else " "
                parts.append(separator)
                cursor += len(separator)
            start = cursor
            parts.append(value)
            cursor += len(value)
            mapped.append(
                _MappedWord(
                    start=start,
                    end=cursor,
                    block=int(block),
                    line=int(line),
                    rect=pymupdf.Rect(float(x0), float(y0), float(x1), float(y1)),
                )
            )
            previous_line = current_line

        return "".join(parts), mapped

    @staticmethod
    def _rectangles_for_detection(detection: _Detection, words: list[_MappedWord]) -> list[Any]:
        hits = [word for word in words if word.start < detection.end and detection.start < word.end]
        grouped: dict[tuple[int, int], Any] = {}
        for word in hits:
            key = (word.block, word.line)
            if key in grouped:
                grouped[key] |= word.rect
            else:
                grouped[key] = pymupdf.Rect(word.rect)

        rectangles: list[Any] = []
        for rect in grouped.values():
            padded = pymupdf.Rect(rect.x0 - 0.8, rect.y0 - 0.4, rect.x1 + 0.8, rect.y1 + 0.4)
            rectangles.append(padded)
        return rectangles

    _CONVERTIBLE_EXTENSIONS = {
        ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".odt",
        ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp",
    }
    _NON_DOCUMENT_OUTPUT_PORTS = {
        "text", "raw_text", "normalized_text", "cleaned_text", "content",
        "data", "metadata", "report", "downloads", "dates", "chunks",
    }

    @classmethod
    def _supported_file_data(
        cls,
        candidate: Any,
        *,
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        file_data = DocumentParserNode._candidate_to_file_data(candidate, provenance=provenance)
        if not file_data:
            return None
        raw_path = str(file_data.get("path") or file_data.get("file_path") or "")
        suffix = Path(raw_path).suffix.lower()
        return file_data if suffix in cls._CONVERTIBLE_EXTENSIONS else None

    @classmethod
    def _resolve_document_artifact(cls, ctx: ExecutionContext) -> dict[str, Any] | None:
        direct = cls._supported_file_data(ctx.get_input("document"))
        if direct:
            direct.setdefault("_selection", "connected_input")
            return direct

        # Accept a document connected under a legacy/non-standard target port.
        for input_name, input_value in ctx.inputs.items():
            if input_name.startswith("__") or input_name in {"document", "text"}:
                continue
            candidate = cls._supported_file_data(
                input_value,
                provenance={"target_input": input_name, "distance": 0},
            )
            if candidate:
                candidate.setdefault("_selection", "connected_input_alias")
                return candidate

        # For Parser -> Masker and similar chains, ignore parser downloads and text
        # outputs, then recover the nearest real document artifact from lineage.
        lineage = ctx.get_input("__upstream_artifacts__", [])
        if isinstance(lineage, list):
            for artifact in lineage:
                if not isinstance(artifact, dict):
                    continue
                output_port = str(artifact.get("output_port") or "")
                if output_port in cls._NON_DOCUMENT_OUTPUT_PORTS:
                    continue
                provenance = {
                    "source_node_id": artifact.get("source_node_id"),
                    "source_node_type": artifact.get("source_node_type"),
                    "source_output_port": output_port,
                    "distance": artifact.get("distance"),
                }
                candidate = cls._supported_file_data(artifact.get("value"), provenance=provenance)
                if candidate:
                    candidate.setdefault("_selection", "nearest_upstream_document")
                    return candidate
        return None

    async def _resolve_pdf(self, ctx: ExecutionContext, config: dict[str, Any]) -> tuple[Path, dict[str, Any], bool]:
        del config  # The masker intentionally has no standalone file configuration.
        file_data = self._resolve_document_artifact(ctx)
        if not file_data:
            raise ValueError(
                "No source document found. Connect a Document Input, File Converter, or a text node whose upstream chain contains a document."
            )

        source_path = Path(str(file_data.get("path") or file_data.get("file_path") or ""))
        if not source_path.exists() or not source_path.is_file():
            raise ValueError(f"Source document not found: {source_path}")

        if source_path.suffix.lower() == ".pdf":
            return source_path, file_data, False

        conversion_dir = self._storage_dir() / "masker" / "converted"
        conversion = await FileConversionService().convert_to_pdf(source_path, conversion_dir)
        converted_path = Path(str(conversion["output_path"]))
        return converted_path, file_data, bool(conversion.get("converted", True))

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()
        output_path: Path | None = None

        try:
            config = self.get_resolved_config()
            enabled = self._enabled_entity_types(config)
            if not enabled:
                result.fail("Select at least one sensitive-data category to mask.")
                return result

            pdf_path, file_data, converted = await self._resolve_pdf(ctx, config)
            source_filename = str(file_data.get("filename") or pdf_path.name)
            style = str(config.get("mask_style", "black"))
            fill = (0, 0, 0) if style == "black" else (1, 1, 1)

            output_dir = self._storage_dir() / "masker"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_filename = f"{self._safe_stem(source_filename)}_masked_{uuid.uuid4().hex[:8]}.pdf"
            output_path = output_dir / output_filename

            by_type: Counter[str] = Counter()
            page_reports: list[dict[str, Any]] = []
            pages_without_text: list[int] = []
            total_rectangles = 0

            document = pymupdf.open(str(pdf_path))
            source_page_count = len(document)
            try:
                for page_index, page in enumerate(document):
                    page_text, word_map = self._page_text_map(page)
                    if not page_text.strip():
                        pages_without_text.append(page_index + 1)
                        continue

                    detections = self.detect_sensitive_spans(page_text, enabled)
                    rectangle_keys: set[tuple[float, float, float, float]] = set()
                    page_rectangles = 0
                    page_counts: Counter[str] = Counter()

                    for detection in detections:
                        rectangles = self._rectangles_for_detection(detection, word_map)
                        if not rectangles:
                            continue
                        applied_for_detection = False
                        for rectangle in rectangles:
                            key = tuple(round(value, 2) for value in (rectangle.x0, rectangle.y0, rectangle.x1, rectangle.y1))
                            if key in rectangle_keys:
                                continue
                            rectangle_keys.add(key)
                            page.add_redact_annot(rectangle, fill=fill, cross_out=False)
                            page_rectangles += 1
                            applied_for_detection = True
                        if applied_for_detection:
                            by_type[detection.entity_type] += 1
                            page_counts[detection.entity_type] += 1

                    if page_rectangles:
                        page.apply_redactions()
                        total_rectangles += page_rectangles
                        page_reports.append(
                            {
                                "page": page_index + 1,
                                "masked_items": sum(page_counts.values()),
                                "redaction_areas": page_rectangles,
                                "by_type": dict(page_counts),
                            }
                        )

                if len(pages_without_text) == len(document):
                    raise ValueError(
                        "The PDF has no searchable text layer. Run OCR before Masker, then use a PDF/OCR flow that preserves word positions."
                    )

                # Remove common document metadata which may itself contain personal data.
                document.set_metadata({})
                document.save(str(output_path), garbage=4, deflate=True, clean=True)
            finally:
                document.close()

            output_document = {
                "id": str(uuid.uuid4()),
                "filename": output_filename,
                "path": str(output_path),
                "file_path": str(output_path),
                "mime_type": "application/pdf",
                "extension": ".pdf",
                "size_bytes": output_path.stat().st_size,
                "download_url": f"/data/storage/masker/{output_filename}",
            }
            provenance = file_data.get("_provenance") if isinstance(file_data.get("_provenance"), dict) else {}
            report = {
                "total_masked": sum(by_type.values()),
                "redaction_areas": total_rectangles,
                "by_type": dict(by_type),
                "pages_with_masks": len(page_reports),
                "pages": page_reports,
            }
            metadata = {
                "source_filename": source_filename,
                "output_filename": output_filename,
                "page_count": source_page_count,
                "pages_without_searchable_text": pages_without_text,
                "converted_to_pdf": converted,
                "mask_style": style,
                "secure_redaction": True,
                "metadata_removed": True,
                "source_node_type": provenance.get("source_node_type"),
                "source_output_port": provenance.get("source_output_port"),
                "selected_source": file_data.get("_selection", "connected_input"),
            }
            result.succeed({"document": output_document, "report": report, "metadata": metadata})
        except Exception as exc:
            if output_path and output_path.exists():
                output_path.unlink(missing_ok=True)
            result.fail(str(exc))

        return result
