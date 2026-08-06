from __future__ import annotations

import importlib.metadata
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.nodes.ingestion.document_parser import DocumentParserNode
from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)


_ARABIC_AND_PERSIAN_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)

_HIJRI_MONTHS = (
    "محرم|صفر|ربيع\\s+(?:الأول|الاول|الثاني|الآخر|الاخر)|"
    "جمادى\\s+(?:الأولى|الاولى|الثانية|الآخرة|الاخرة)|"
    "رجب|شعبان|رمضان|شوال|ذو\\s+القعدة|ذي\\s+القعدة|ذو\\s+الحجة|ذي\\s+الحجة"
)
_HIJRI_MARKER_RE = re.compile(r"(?:هـ|هجر(?:ي|ية)|هجرياً|هجريا)", re.IGNORECASE)
_HIJRI_MONTH_RE = re.compile(_HIJRI_MONTHS, re.IGNORECASE)
_HIJRI_NUMERIC_RE = re.compile(
    r"(?<!\d)(?:[0-3]?\d)[./-](?:[01]?\d)[./-](?:1[2-6]\d{2})"
    r"(?:\s*(?:هـ|هجر(?:ي|ية)|هجرياً|هجريا))?"
    r"(?:\s+(?:[0-2]?\d):[0-5]\d(?:\s*(?:ص|م|صباح(?:اً|ا)?|مساء(?:ً|ا)?))?)?",
    re.IGNORECASE,
)
_HIJRI_WORD_RE = re.compile(
    rf"(?<!\w)(?:[0-3]?\d)\s+(?:{_HIJRI_MONTHS})\s+(?:1[2-6]\d{{2}})"
    r"(?:\s*(?:هـ|هجر(?:ي|ية)|هجرياً|هجريا))?"
    r"(?:\s+(?:[0-2]?\d):[0-5]\d(?:\s*(?:ص|م|صباح(?:اً|ا)?|مساء(?:ً|ا)?))?)?",
    re.IGNORECASE,
)

_TIME_HINT_RE = re.compile(
    r"\b\d{1,2}:\d{2}(?::\d{2})?\b|\b(?:am|pm)\b|(?:صباح|مساء|ظهراً|ظهرا|ليلاً|ليلا)",
    re.IGNORECASE,
)
_RELATIVE_HINT_RE = re.compile(
    r"\b(?:today|tomorrow|yesterday|ago|next|last|now|today's|"
    r"aujourd'hui|demain|hier|prochain|prochaine|dernier|dernière|il y a|"
    r"اليوم|غد(?:اً|ا)?|أمس|امس|بعد|قبل|منذ|الآن|الان|القادم|الماضي)\b",
    re.IGNORECASE,
)
_DATE_SIGNAL_RE = re.compile(
    r"[/.-]|\b\d{4}\b|[A-Za-zÀ-ÿ]{3,}|[\u0600-\u06FF]{3,}",
    re.UNICODE,
)


class DateNormalizerNode(BaseNode):
    """Detect dates in text or document content and normalize their format.

    The node accepts either text produced by an upstream node or a document
    artifact. PDF files are parsed internally; other supported documents reuse
    the same complete parsing helpers as the Document Parser node. Language and
    calendar detection stay automatic so the user only chooses the output format.
    """

    type = "date-normalizer"
    name = "Date Normalizer"
    category = "normalization"
    icon = "📅"
    color = "#8b5cf6"
    description = "Detect dates in text or documents and convert them to a selected format"
    version = "1.2.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Text produced by an upstream parser, OCR, cleaner, or other text node",
            required=False,
        ),
        Port(
            name="document",
            type=PortType.DOCUMENT,
            label="Document",
            description="PDF or another supported document artifact to parse before normalizing dates",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="normalized_text",
            type=PortType.TEXT,
            label="Normalized Text",
            description="Input content with detected dates converted to the selected format",
        ),
        Port(
            name="dates",
            type=PortType.JSON,
            label="Normalized Dates",
            description="Detected dates with source spans and normalized values",
        ),
        Port(
            name="metadata",
            type=PortType.JSON,
            label="Metadata",
            description="Input source, parsing engine, selected format, and processing statistics",
        ),
    ]

    config_fields = [
        ConfigField(
            key="output_format",
            label="Date Format",
            type="select",
            required=False,
            default="YYYY-MM-DD",
            options=["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"],
            description="Format used for every detected date. The time is kept automatically when present.",
        ),
        ConfigField(
            key="replace_in_text",
            label="Replace Dates in Text",
            type="boolean",
            required=False,
            default=True,
            description="Replace dates in the returned text. Disable to keep the original text and only return the detected dates list.",
        ),
    ]

    _DEFAULT_LANGUAGES = ["fr", "en", "ar"]
    _TEXT_KEYS = ("text", "raw_text", "full_text", "cleaned_text", "normalized_text", "content")

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            source = self._resolve_source(ctx)
            if not source:
                result.fail(
                    "No input found. Connect a text-producing node (for example Document Parser or OCR) "
                    "or connect a PDF/document input."
                )
                return result

            text = str(source.get("text") or "")
            if not text.strip():
                if source.get("requires_ocr"):
                    result.fail(
                        "The PDF does not contain an extractable text layer. Connect an OCR node before Date Normalizer."
                    )
                else:
                    result.fail("The connected input does not contain any text to normalize.")
                return result

            max_text_length = 2_000_000
            if len(text) > max_text_length:
                result.fail(f"Text is too long ({len(text):,} characters). Maximum is {max_text_length:,}.")
                return result

            normalized_input = self.normalize_digits(text)
            internal_config = {
                **config,
                "date_order": "DMY",
                "prefer_dates_from": "current_period",
                "calendar": "auto",
                "timezone": "UTC",
                "to_timezone": "",
                "timezone_aware": False,
                "strict_parsing": False,
            }
            settings = self.build_settings(internal_config, None)

            detections: list[dict[str, Any]] = []
            detections.extend(
                self._find_hijri_dates(
                    normalized_input,
                    calendar_mode="auto",
                    config=internal_config,
                )
            )
            detections.extend(
                self._find_gregorian_dates(
                    normalized_input,
                    languages=list(self._DEFAULT_LANGUAGES),
                    settings=settings,
                    config=internal_config,
                    occupied=[(item["start"], item["end"]) for item in detections],
                )
            )

            detections = self._deduplicate_and_sort(detections)[:1000]
            for item in detections:
                item["original"] = text[int(item["start"]):int(item["end"])]

            replace_in_text = bool(config.get("replace_in_text", True))
            normalized_text = self.replace_spans(text, detections) if replace_in_text else text

            try:
                engine_version = importlib.metadata.version("dateparser")
            except importlib.metadata.PackageNotFoundError:
                engine_version = "unknown"

            metadata = {
                "engine": "dateparser",
                "engine_version": engine_version,
                "input_type": source.get("input_type", "text"),
                "source_filename": source.get("filename"),
                "source_node_id": source.get("source_node_id"),
                "source_node_type": source.get("source_node_type"),
                "source_output_port": source.get("source_output_port"),
                "document_parser_engine": source.get("parser_engine"),
                "document_pages": source.get("page_count"),
                "requires_ocr": bool(source.get("requires_ocr", False)),
                "dates_found": len(detections),
                "output_format": config.get("output_format", "YYYY-MM-DD"),
                "replace_in_text": replace_in_text,
                "input_characters": len(text),
            }

            result.succeed(
                {
                    "normalized_text": normalized_text,
                    "dates": detections,
                    "metadata": metadata,
                }
            )
        except ImportError as exc:
            result.fail(
                "Date Normalizer dependency is missing. Run run.bat again or install "
                "'dateparser[calendars]>=1.4.1'. Details: " + str(exc)
            )
        except Exception as exc:
            result.fail(f"Date normalization failed: {exc}")

        return result

    @classmethod
    def _resolve_source(cls, ctx: ExecutionContext) -> dict[str, Any] | None:
        direct_text = cls._extract_text(ctx.get_input("text"))
        if direct_text:
            return {
                "text": direct_text,
                "input_type": "text",
                **cls._source_metadata(ctx, target_port="text"),
            }

        file_data = DocumentParserNode._resolve_file_data(ctx, {})
        if file_data:
            path_value = file_data.get("path") or file_data.get("file_path")
            if path_value:
                file_path = Path(str(path_value))
                parsed = cls._parse_document(file_path)
                provenance = file_data.get("_provenance") if isinstance(file_data.get("_provenance"), dict) else {}
                source_meta = cls._source_metadata(ctx, target_port="document")
                return {
                    "text": parsed["text"],
                    "input_type": "document",
                    "filename": str(file_data.get("filename") or file_path.name),
                    "parser_engine": parsed.get("parser_engine"),
                    "page_count": parsed.get("page_count"),
                    "requires_ocr": parsed.get("requires_ocr", False),
                    "source_node_id": source_meta.get("source_node_id") or provenance.get("source_node_id"),
                    "source_node_type": source_meta.get("source_node_type") or provenance.get("source_node_type"),
                    "source_output_port": source_meta.get("source_output_port") or provenance.get("source_output_port"),
                }

        lineage = ctx.get_input("__upstream_artifacts__", [])
        if isinstance(lineage, list):
            for artifact in lineage:
                if not isinstance(artifact, dict):
                    continue
                candidate = cls._extract_text(artifact.get("value"))
                if candidate:
                    return {
                        "text": candidate,
                        "input_type": "text",
                        "source_node_id": artifact.get("source_node_id"),
                        "source_node_type": artifact.get("source_node_type"),
                        "source_output_port": artifact.get("output_port"),
                    }
        return None

    @classmethod
    def _extract_text(cls, value: Any) -> str | None:
        if isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return None
            try:
                if Path(candidate).exists():
                    return None
            except (OSError, ValueError):
                pass
            return value
        if isinstance(value, dict):
            for key in cls._TEXT_KEYS:
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate
                if isinstance(candidate, dict):
                    nested = cls._extract_text(candidate)
                    if nested:
                        return nested
        return None

    @staticmethod
    def _source_metadata(ctx: ExecutionContext, *, target_port: str) -> dict[str, Any]:
        sources = ctx.get_input("__input_sources__", [])
        if isinstance(sources, list):
            for item in sources:
                if not isinstance(item, dict) or item.get("target_port") != target_port:
                    continue
                return {
                    "source_node_id": item.get("source_node_id"),
                    "source_node_type": item.get("source_node_type"),
                    "source_output_port": item.get("source_port"),
                }
        return {}

    @staticmethod
    def _parse_document(path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            raise ValueError(f"Input document not found: {path}")

        extension = path.suffix.lower()
        if extension == ".pdf":
            text, data = DocumentParserNode._parse_pdf(path, preserve_page_breaks=True)
            return {
                "text": text,
                "parser_engine": "pypdf",
                "page_count": len(data.get("pages", [])),
                "requires_ocr": bool(data.get("requires_ocr", False)),
            }
        if extension == ".docx":
            text, _ = DocumentParserNode._parse_docx(path, include_tables=True, include_headers_footers=True)
            return {"text": text, "parser_engine": "python-docx", "page_count": None, "requires_ocr": False}
        if extension in {".xlsx", ".xlsm"}:
            text, _ = DocumentParserNode._parse_xlsx(path, include_tables=True, sheet_name="", max_rows=None)
            return {"text": text, "parser_engine": "openpyxl", "page_count": None, "requires_ocr": False}
        if extension == ".csv":
            text, _ = DocumentParserNode._parse_csv(path, include_tables=True, max_rows=None)
            return {"text": text, "parser_engine": "python-csv", "page_count": None, "requires_ocr": False}
        if extension in {".txt", ".md"}:
            return {
                "text": DocumentParserNode._read_text_file(path),
                "parser_engine": "python-text",
                "page_count": None,
                "requires_ocr": False,
            }
        raise ValueError(
            f"Unsupported document type '{extension}'. Connect Document Parser or OCR before Date Normalizer."
        )

    @staticmethod
    def normalize_digits(text: str) -> str:
        """Translate Arabic-Indic and Persian digits without changing offsets."""
        return text.translate(_ARABIC_AND_PERSIAN_DIGITS)

    @staticmethod
    def parse_languages(value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, (list, tuple, set)):
            raw = [str(item) for item in value]
        else:
            raw = re.split(r"[,;\s]+", str(value))
        languages: list[str] = []
        for item in raw:
            code = item.strip().lower().replace("_", "-")
            if not code or code in languages:
                continue
            if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})?", code):
                raise ValueError(f"Invalid language code '{item}'. Use ISO codes such as ar, fr or en.")
            languages.append(code)
        return languages or None

    @staticmethod
    def parse_relative_base(value: Any) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("Relative Base must be an ISO date/time, for example 2026-08-02T12:00:00+01:00") from exc

    @staticmethod
    def build_settings(config: dict[str, Any], relative_base: datetime | None) -> dict[str, Any]:
        settings: dict[str, Any] = {
            "DATE_ORDER": str(config.get("date_order", "DMY")),
            "PREFER_LOCALE_DATE_ORDER": False,
            "PREFER_DATES_FROM": str(config.get("prefer_dates_from", "current_period")),
            "TIMEZONE": str(config.get("timezone", "UTC") or "UTC"),
            "RETURN_AS_TIMEZONE_AWARE": bool(config.get("timezone_aware", True)),
            "STRICT_PARSING": bool(config.get("strict_parsing", False)),
            "NORMALIZE": True,
            "USE_GIVEN_LANGUAGE_ORDER": True,
        }
        to_timezone = str(config.get("to_timezone", "") or "").strip()
        if to_timezone:
            settings["TO_TIMEZONE"] = to_timezone
        if relative_base:
            settings["RELATIVE_BASE"] = relative_base
        return settings

    def _find_gregorian_dates(
        self,
        text: str,
        *,
        languages: list[str] | None,
        settings: dict[str, Any],
        config: dict[str, Any],
        occupied: list[tuple[int, int]],
    ) -> list[dict[str, Any]]:
        from dateparser.search import search_dates

        # A separate pass per known language improves mixed-language text such as
        # Arabic + French in one paragraph. A single automatic-detection pass is
        # kept when no language preference is supplied.
        search_passes: list[list[str] | None] = (
            [[language] for language in languages] if languages else [None]
        )

        detections: list[dict[str, Any]] = []
        all_occupied = list(occupied)
        for pass_languages in search_passes:
            found = search_dates(
                text,
                languages=pass_languages,
                settings=settings,
                add_detected_language=True,
            ) or []

            cursor = 0
            for item in found:
                if len(item) >= 3:
                    matched, date_obj, detected_language = item[0], item[1], item[2]
                else:
                    matched, date_obj = item[0], item[1]
                    detected_language = pass_languages[0] if pass_languages else None

                matched = str(matched)
                if not matched.strip() or not isinstance(date_obj, datetime):
                    continue
                if not self._looks_like_date_expression(matched):
                    continue

                start = text.find(matched, cursor)
                if start < 0:
                    start = text.find(matched)
                if start < 0:
                    continue
                end = start + len(matched)
                cursor = end
                if self._overlaps(start, end, all_occupied):
                    continue

                detections.append(
                    self._make_detection(
                        original=matched,
                        date_obj=date_obj,
                        start=start,
                        end=end,
                        language=detected_language or (pass_languages[0] if pass_languages else None),
                        calendar="gregorian",
                        config=config,
                    )
                )
                all_occupied.append((start, end))
        return detections

    def _find_hijri_dates(
        self,
        text: str,
        *,
        calendar_mode: str,
        config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        from dateparser.calendars.hijri import HijriCalendar

        candidates: list[tuple[int, int, str]] = []
        for pattern in (_HIJRI_WORD_RE, _HIJRI_NUMERIC_RE):
            for match in pattern.finditer(text):
                candidate = match.group(0)
                if calendar_mode == "auto" and not self._is_probably_hijri(candidate):
                    continue
                candidates.append((match.start(), match.end(), candidate))

        detections: list[dict[str, Any]] = []
        occupied: list[tuple[int, int]] = []
        for start, end, candidate in sorted(candidates, key=lambda value: (value[0], -(value[1] - value[0]))):
            if self._overlaps(start, end, occupied):
                continue
            try:
                date_data = HijriCalendar(candidate).get_date()
                date_obj = getattr(date_data, "date_obj", None)
            except Exception:
                continue
            if not isinstance(date_obj, datetime):
                continue
            detections.append(
                self._make_detection(
                    original=candidate,
                    date_obj=date_obj,
                    start=start,
                    end=end,
                    language="ar",
                    calendar="hijri",
                    config=config,
                )
            )
            occupied.append((start, end))
        return detections

    @staticmethod
    def _is_probably_hijri(candidate: str) -> bool:
        if _HIJRI_MARKER_RE.search(candidate) or _HIJRI_MONTH_RE.search(candidate):
            return True
        years = [int(value) for value in re.findall(r"(?<!\d)(1[2-6]\d{2})(?!\d)", candidate)]
        return any(1200 <= year <= 1600 for year in years)

    @staticmethod
    def _looks_like_date_expression(value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        if stripped.isdigit() and len(stripped) <= 4:
            return False
        return bool(_DATE_SIGNAL_RE.search(stripped) or _RELATIVE_HINT_RE.search(stripped))

    def _make_detection(
        self,
        *,
        original: str,
        date_obj: datetime,
        start: int,
        end: int,
        language: str | None,
        calendar: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        has_time = bool(_TIME_HINT_RE.search(original))
        normalized = self.format_datetime(date_obj, config, has_time=has_time)
        return {
            "original": original,
            "normalized": normalized,
            "iso_date": date_obj.date().isoformat(),
            "iso_datetime": date_obj.isoformat(),
            "detected_language": language,
            "calendar": calendar,
            "start": start,
            "end": end,
            "has_time": has_time,
            "is_relative": bool(_RELATIVE_HINT_RE.search(original)),
        }

    @staticmethod
    def format_datetime(value: datetime, config: dict[str, Any], *, has_time: bool = False) -> str:
        selected = str(config.get("output_format", "YYYY-MM-DD"))
        date_formats = {
            "YYYY-MM-DD": "%Y-%m-%d",
            "DD/MM/YYYY": "%d/%m/%Y",
            "MM/DD/YYYY": "%m/%d/%Y",
        }
        date_format = date_formats.get(selected, "%Y-%m-%d")
        if has_time:
            return value.strftime(f"{date_format} %H:%M:%S")
        return value.strftime(date_format)

    @staticmethod
    def _overlaps(start: int, end: int, occupied: list[tuple[int, int]]) -> bool:
        return any(start < other_end and end > other_start for other_start, other_end in occupied)

    @staticmethod
    def _deduplicate_and_sort(detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(detections, key=lambda item: (int(item["start"]), -int(item["end"])))
        kept: list[dict[str, Any]] = []
        occupied: list[tuple[int, int]] = []
        for item in ordered:
            start, end = int(item["start"]), int(item["end"])
            if DateNormalizerNode._overlaps(start, end, occupied):
                continue
            kept.append(item)
            occupied.append((start, end))
        return kept

    @staticmethod
    def replace_spans(original_text: str, detections: list[dict[str, Any]]) -> str:
        normalized = original_text
        for item in sorted(detections, key=lambda entry: int(entry["start"]), reverse=True):
            start, end = int(item["start"]), int(item["end"])
            normalized = normalized[:start] + str(item["normalized"]) + normalized[end:]
        return normalized

    @staticmethod
    def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(maximum, parsed))
