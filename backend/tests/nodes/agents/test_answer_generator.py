from __future__ import annotations

import json

import pytest

from backend.nodes.agents.answer_generator import AnswerGeneratorNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return AnswerGeneratorNode(node_id="test-answer-gen-1", config={})


def test_node_definition(node: AnswerGeneratorNode):
    assert node.type == "answer-generator"
    assert node.name == "Answer Generator Agent"
    assert node.category == "agents"
    assert len(node.inputs) == 3
    input_names = {p.name for p in node.inputs}
    assert input_names == {"question", "agent_results", "evidence"}
    assert len(node.outputs) == 2
    output_names = {p.name for p in node.outputs}
    assert output_names == {"answer", "confidence"}
    assert len(node.config_fields) == 1


@pytest.mark.asyncio
async def test_execute_fails_with_no_question(node: AnswerGeneratorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-answer-gen-1",
        inputs={"agent_results": {"table_agent": "150"}},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No question provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_with_no_agent_results(node: AnswerGeneratorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-answer-gen-1",
        inputs={"question": "What is the total?"},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No agent results provided" in result.error


@pytest.mark.asyncio
async def test_execute_with_mock_llm_returns_answer(node: AnswerGeneratorNode, monkeypatch):
    async def fake_generate(self, prompt, system_prompt="", temperature=0.0, max_tokens=4096, disable_thinking=True):
        return json.dumps({"answer": "The total amount is 150.", "confidence": "high"})

    from backend.services.llm import LLMService
    monkeypatch.setattr(LLMService, "generate", fake_generate)

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-answer-gen-1",
        inputs={
            "question": "What is the total amount?",
            "agent_results": {"table_agent": {"answer": "150"}},
            "evidence": {"table": {"rows": [["A", 100], ["B", 50]]}},
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["answer"] == "The total amount is 150."
    assert result.outputs["confidence"] == "high"


def test_to_definition_returns_correct_shape(node: AnswerGeneratorNode):
    definition = node.to_definition()
    assert definition["type"] == "answer-generator"
    assert definition["name"] == "Answer Generator Agent"
    assert definition["category"] == "agents"
    assert len(definition["inputs"]) == 3
    assert len(definition["outputs"]) == 2
    assert len(definition["config_fields"]) == 1