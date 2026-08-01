from __future__ import annotations

import pytest

from backend.nodes.analysis.translator import TranslatorNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return TranslatorNode(node_id="test-translator-1", config={})


def test_node_definition(node: TranslatorNode):
    assert node.type == "translator"
    assert node.name == "Translator"
    assert node.category == "analysis"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "text"
    assert len(node.outputs) == 1
    assert node.outputs[0].name == "translated_text"
    assert len(node.config_fields) == 2


@pytest.mark.asyncio
async def test_execute_skips_when_same_language(node: TranslatorNode):
    node = TranslatorNode(node_id="test-translator-1", config={"from_language": "en", "to_language": "en"})

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-translator-1",
        inputs={"text": "Hello world"},
        config={"from_language": "en", "to_language": "en"},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["translated_text"] == "Hello world"


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: TranslatorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-translator-1",
        inputs={},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No text provided" in result.error


def test_to_definition_returns_correct_shape(node: TranslatorNode):
    definition = node.to_definition()
    assert definition["type"] == "translator"
    assert definition["name"] == "Translator"
    assert definition["category"] == "analysis"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 1
    assert len(definition["config_fields"]) == 2