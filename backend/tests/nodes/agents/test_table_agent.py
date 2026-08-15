# backend/tests/nodes/agents/test_table_agent.py
from __future__ import annotations

import json

import pytest

from backend.nodes.agents.table_agent import TableAgentNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return TableAgentNode(node_id="test-table-agent-1", config={})


def test_node_definition(node: TableAgentNode):
    assert node.type == "table-agent"
    assert node.name == "Table Agent"
    assert node.category == "agents"
    assert len(node.inputs) == 2
    input_names = {p.name for p in node.inputs}
    assert input_names == {"table", "question"}
    assert len(node.outputs) == 2
    output_names = {p.name for p in node.outputs}
    assert output_names == {"answer", "reasoning"}
    assert len(node.config_fields) == 1


@pytest.mark.asyncio
async def test_execute_fails_with_no_table(node: TableAgentNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-table-agent-1",
        inputs={"question": "What is the total?"},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No table provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_with_no_question(node: TableAgentNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-table-agent-1",
        inputs={"table": {"rows": [["Total", "100"]]}},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No question provided" in result.error


@pytest.mark.asyncio
async def test_execute_with_mock_llm_returns_answer(node: TableAgentNode, monkeypatch):
    async def fake_generate(self, prompt, system_prompt="", temperature=0.0, max_tokens=4096, disable_thinking=True):
        return json.dumps({"answer": "150", "reasoning": "Summed the Amount column: 100 + 50 = 150"})

    from backend.services.llm import LLMService
    monkeypatch.setattr(LLMService, "generate", fake_generate)

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-table-agent-1",
        inputs={
            "table": {"columns": ["Item", "Amount"], "rows": [["A", 100], ["B", 50]]},
            "question": "What is the total amount?",
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["answer"] == "150"
    assert "150" in result.outputs["reasoning"]


def test_to_definition_returns_correct_shape(node: TableAgentNode):
    definition = node.to_definition()
    assert definition["type"] == "table-agent"
    assert definition["name"] == "Table Agent"
    assert definition["category"] == "agents"
    assert len(definition["inputs"]) == 2
    assert len(definition["outputs"]) == 2
    assert len(definition["config_fields"]) == 1