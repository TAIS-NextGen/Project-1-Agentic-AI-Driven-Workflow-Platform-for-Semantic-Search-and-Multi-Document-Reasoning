from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.nodes.ingestion.document_parser import DocumentParserNode
from backend.nodes.normalization.date_normalizer import DateNormalizerNode
from backend.sdk import ExecutionContext, NodeStatus


def install_fake_dateparser(monkeypatch: pytest.MonkeyPatch) -> None:
    dateparser_module = types.ModuleType("dateparser")
    search_module = types.ModuleType("dateparser.search")
    calendars_module = types.ModuleType("dateparser.calendars")
    hijri_module = types.ModuleType("dateparser.calendars.hijri")

    def search_dates(text, languages=None, settings=None, add_detected_language=False):
        language = languages[0] if languages else "auto"
        results = []
        if language == "ar" and "غداً" in text:
            results.append(("غداً", datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc), "ar"))
        if language == "fr" and "12/08/2026" in text:
            results.append(("12/08/2026", datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc), "fr"))
        if language == "en" and "tomorrow" in text:
            results.append(("tomorrow", datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc), "en"))
        return results

    class FakeHijriDateData:
        date_obj = datetime(2015, 10, 30, 20, 30, tzinfo=timezone.utc)

    class FakeHijriCalendar:
        def __init__(self, value):
            self.value = value

        def get_date(self):
            return FakeHijriDateData()

    search_module.search_dates = search_dates
    hijri_module.HijriCalendar = FakeHijriCalendar
    dateparser_module.search = search_module
    dateparser_module.calendars = calendars_module
    calendars_module.hijri = hijri_module

    monkeypatch.setitem(sys.modules, "dateparser", dateparser_module)
    monkeypatch.setitem(sys.modules, "dateparser.search", search_module)
    monkeypatch.setitem(sys.modules, "dateparser.calendars", calendars_module)
    monkeypatch.setitem(sys.modules, "dateparser.calendars.hijri", hijri_module)


@pytest.mark.asyncio
async def test_text_from_parser_is_normalized_and_source_is_reported(monkeypatch):
    install_fake_dateparser(monkeypatch)
    source = "Rendez-vous le 12/08/2026"
    node = DateNormalizerNode("dates", {"output_format": "YYYY-MM-DD", "replace_in_text": True})
    ctx = ExecutionContext(
        "wf",
        "dates",
        inputs={
            "text": source,
            "__input_sources__": [
                {
                    "source_node_id": "parser-1",
                    "source_node_type": "document-parser",
                    "source_port": "text",
                    "target_port": "text",
                }
            ],
        },
        config=node.get_resolved_config(),
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["normalized_text"] == "Rendez-vous le 2026-08-12"
    assert result.outputs["metadata"]["input_type"] == "text"
    assert result.outputs["metadata"]["source_node_type"] == "document-parser"
    assert result.outputs["metadata"]["source_output_port"] == "text"


@pytest.mark.asyncio
async def test_output_format_is_the_only_visible_date_choice(monkeypatch):
    install_fake_dateparser(monkeypatch)
    node = DateNormalizerNode("dates", {"output_format": "DD/MM/YYYY", "replace_in_text": True})
    result = await node.execute(
        ExecutionContext("wf", "dates", inputs={"text": "tomorrow"}, config=node.get_resolved_config())
    )

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["normalized_text"] == "03/08/2026"
    assert result.outputs["dates"][0]["normalized"] == "03/08/2026"


@pytest.mark.asyncio
async def test_pdf_document_is_parsed_before_date_normalization(monkeypatch, tmp_path: Path):
    install_fake_dateparser(monkeypatch)
    pdf_path = tmp_path / "planning.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test placeholder")

    def fake_parse_pdf(path: Path, preserve_page_breaks: bool):
        assert path == pdf_path
        assert preserve_page_breaks is True
        return "Planning du 12/08/2026", {
            "pages": [{"page": 1, "text": "Planning du 12/08/2026"}],
            "empty_pages": [],
            "requires_ocr": False,
        }

    monkeypatch.setattr(DocumentParserNode, "_parse_pdf", staticmethod(fake_parse_pdf))

    node = DateNormalizerNode("dates", {"output_format": "YYYY-MM-DD"})
    result = await node.execute(
        ExecutionContext(
            "wf",
            "dates",
            inputs={
                "document": {"path": str(pdf_path), "filename": pdf_path.name},
                "__input_sources__": [
                    {
                        "source_node_id": "upload-1",
                        "source_node_type": "document-upload",
                        "source_port": "document",
                        "target_port": "document",
                    }
                ],
            },
            config=node.get_resolved_config(),
        )
    )

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["normalized_text"] == "Planning du 2026-08-12"
    assert result.outputs["metadata"]["input_type"] == "document"
    assert result.outputs["metadata"]["source_filename"] == "planning.pdf"
    assert result.outputs["metadata"]["document_parser_engine"] == "pypdf"
    assert result.outputs["metadata"]["document_pages"] == 1


@pytest.mark.asyncio
async def test_pdf_without_text_layer_requests_ocr(monkeypatch, tmp_path: Path):
    install_fake_dateparser(monkeypatch)
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test placeholder")
    monkeypatch.setattr(
        DocumentParserNode,
        "_parse_pdf",
        staticmethod(lambda path, preserve_page_breaks: ("", {"pages": [{}], "requires_ocr": True})),
    )

    node = DateNormalizerNode("dates", {})
    result = await node.execute(
        ExecutionContext(
            "wf",
            "dates",
            inputs={"document": {"path": str(pdf_path), "filename": pdf_path.name}},
            config=node.get_resolved_config(),
        )
    )

    assert result.status == NodeStatus.FAILURE
    assert "OCR" in (result.error or "")


@pytest.mark.asyncio
async def test_hijri_date_still_works_without_visible_calendar_configuration(monkeypatch):
    install_fake_dateparser(monkeypatch)
    node = DateNormalizerNode("hijri", {"output_format": "YYYY-MM-DD"})
    result = await node.execute(
        ExecutionContext(
            "wf",
            "hijri",
            inputs={"text": "الموعد 17-01-1437 هـ 08:30 مساءً"},
            config=node.get_resolved_config(),
        )
    )

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["dates"][0]["calendar"] == "hijri"
    assert result.outputs["dates"][0]["normalized"] == "2015-10-30 20:30:00"


@pytest.mark.asyncio
async def test_empty_input_returns_clear_failure(monkeypatch):
    install_fake_dateparser(monkeypatch)
    node = DateNormalizerNode("empty", {})
    result = await node.execute(ExecutionContext("wf", "empty", config=node.get_resolved_config()))
    assert result.status == NodeStatus.FAILURE
    assert "Connect a text-producing node" in (result.error or "")


def test_node_contract_is_simple_and_accepts_text_or_document():
    assert DateNormalizerNode.description == "Detect dates in text or documents and convert them to a selected format"
    assert [port.name for port in DateNormalizerNode.inputs] == ["text", "document"]
    assert [field.key for field in DateNormalizerNode.config_fields] == ["output_format", "replace_in_text"]


def test_digit_translation_preserves_offsets():
    source = "١٢/٠٨/٢٠٢٦ and ۱۴۰۵"
    normalized = DateNormalizerNode.normalize_digits(source)
    assert normalized == "12/08/2026 and 1405"
    assert len(normalized) == len(source)


def test_format_keeps_time_when_present():
    value = datetime(2026, 8, 12, 10, 30, tzinfo=timezone.utc)
    assert DateNormalizerNode.format_datetime(value, {"output_format": "YYYY-MM-DD"}, has_time=False) == "2026-08-12"
    assert DateNormalizerNode.format_datetime(value, {"output_format": "DD/MM/YYYY"}, has_time=True) == "12/08/2026 10:30:00"
