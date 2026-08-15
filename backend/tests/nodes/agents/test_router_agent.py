from __future__ import annotations

import json

import pytest

from backend.nodes.agents.router_agent import RouterAgentNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return RouterAgentNode(node_id="test-router-1", config={})


def test_node_definition(node: RouterAgentNode):
    assert node.type == "router-agent"
    assert node.name == "Router Agent"
    assert node.category == "agents"
    assert len(node.inputs) == 2
    input_names = {p.name for p in node.inputs}
    assert input_names == {"plan", "document_structure"}
    assert len(node.outputs) == 1
    assert node.outputs[0].name == "steps"
    assert len(node.config_fields) == 1


@pytest.mark.asyncio
async def test_execute_fails_with_no_plan(node: RouterAgentNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-router-1",
        inputs={},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No task plan provided" in result.error


@pytest.mark.asyncio
async def test_execute_with_mock_llm_returns_steps(node: RouterAgentNode, monkeypatch):
    # LLMService falls back to a mock response when no API key/base_url is set,
    # so we monkeypatch generate() to return a realistic structured JSON response
    # instead of the default "[Mock LLM response for: ...]" plain-text fallback.
    async def fake_generate(self, prompt, system_prompt="", temperature=0.0, max_tokens=4096, disable_thinking=True):
        return json.dumps({
            "steps": [
                {"order": 1, "agent": "table_agent", "reason": "Plan requires table reasoning"},
                {"order": 2, "agent": "summarizer", "reason": "Plan requires a summary"},
            ]
        })

    from backend.services.llm import LLMService
    monkeypatch.setattr(LLMService, "generate", fake_generate)

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-router-1",
        inputs={
            "plan": {"goal": "Summarize the invoice table"},
            "document_structure": {"tables": 1, "paragraphs": 3},
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert len(result.outputs["steps"]) == 2
    assert result.outputs["steps"][0]["agent"] == "table_agent"
    assert result.outputs["steps"][1]["agent"] == "summarizer"


@pytest.mark.asyncio
async def test_execute_handles_malformed_llm_response(node: RouterAgentNode, monkeypatch):
    async def fake_generate(self, prompt, system_prompt="", temperature=0.0, max_tokens=4096, disable_thinking=True):
        return "this is not valid json at all"

    from backend.services.llm import LLMService
    monkeypatch.setattr(LLMService, "generate", fake_generate)

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-router-1",
        inputs={"plan": {"goal": "Do something"}},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS
    assert result.outputs["steps"] == []


def test_to_definition_returns_correct_shape(node: RouterAgentNode):
    definition = node.to_definition()
    assert definition["type"] == "router-agent"
    assert definition["name"] == "Router Agent"
    assert definition["category"] == "agents"
    assert len(definition["inputs"]) == 2
    assert len(definition["outputs"]) == 1
    assert len(definition["config_fields"]) == 1