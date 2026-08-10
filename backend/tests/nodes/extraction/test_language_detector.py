from __future__ import annotations

import os
from pathlib import Path
import pytest

from backend.nodes.extraction.language_detector import LanguageDetectorNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return LanguageDetectorNode(node_id="test-lang-1", config={})


def test_node_definition(node: LanguageDetectorNode):
    assert node.type == "language-detector"
    assert node.name == "Language Detector"
    assert node.category == "extraction"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "text"
    assert len(node.outputs) == 2
    output_names = {p.name for p in node.outputs}
    assert output_names == {"languages", "languages_str"}
    assert len(node.config_fields) == 4


@pytest.mark.asyncio
async def test_detect_single_language_english(node: LanguageDetectorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-lang-1",
        inputs={"text": "This is a simple English sentence to test the language detector node."},
        config={"detection_mode": "document", "min_probability": 0.1},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert "en" in result.outputs["languages_str"]
    langs = result.outputs["languages"]
    assert len(langs) > 0
    assert langs[0]["lang"] == "en"
    assert langs[0]["probability"] > 0.8


@pytest.mark.asyncio
async def test_detect_single_language_french(node: LanguageDetectorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-lang-1",
        inputs={"text": "Ceci est une simple phrase en français pour tester le détecteur de langue."},
        config={"detection_mode": "document", "min_probability": 0.1},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert "fr" in result.outputs["languages_str"]
    langs = result.outputs["languages"]
    assert len(langs) > 0
    assert langs[0]["lang"] == "fr"
    assert langs[0]["probability"] > 0.8


@pytest.mark.asyncio
async def test_detect_multi_language_paragraph(node: LanguageDetectorNode):
    multi_lang_text = (
        "Bonjour tout le monde. J'espère que vous allez bien.\n\n"
        "Hello everyone. I hope you are doing well today.\n\n"
        "Hello again, testing another English paragraph."
    )
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-lang-1",
        inputs={"text": multi_lang_text},
        config={"detection_mode": "paragraph", "min_probability": 0.2, "max_languages": 3},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    languages_str = result.outputs["languages_str"]
    assert "fr" in languages_str
    assert "en" in languages_str
    
    langs = result.outputs["languages"]
    # Should have both french and english
    lang_codes = [item["lang"] for item in langs]
    assert "en" in lang_codes
    assert "fr" in lang_codes


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: LanguageDetectorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-lang-1",
        inputs={},
        config={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No text provided" in result.error


@pytest.mark.asyncio
async def test_execute_with_file_id(node: LanguageDetectorNode, tmp_path: Path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))

    txt_file = upload_dir / "test-file.txt"
    txt_file.write_text("Ceci est du texte écrit en français.", encoding="utf-8")
    file_id = txt_file.stem

    node_with_config = LanguageDetectorNode(
        node_id="test-lang-2",
        config={"file_id": file_id},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-lang-2",
        inputs={},
        config={"file_id": file_id},
    )

    result = await node_with_config.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert "fr" in result.outputs["languages_str"]


def test_to_definition_returns_correct_shape(node: LanguageDetectorNode):
    definition = node.to_definition()
    assert definition["type"] == "language-detector"
    assert definition["name"] == "Language Detector"
    assert definition["category"] == "extraction"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 2
    assert len(definition["config_fields"]) == 4
