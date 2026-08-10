import pytest
from unittest.mock import AsyncMock, patch

from backend.sdk import ExecutionContext
from backend.nodes.agents.summarizer import SummarizerNode


@pytest.fixture
def node():
    return SummarizerNode(node_id="test-summarizer-1")


def test_node_definition(node: SummarizerNode):
    assert node.type == "summarizer"
    assert node.name == "Summarizer Agent"
    assert node.category == "agents"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "text"
    assert len(node.outputs) == 1
    assert node.outputs[0].name == "summary"
    assert len(node.config_fields) == 2


@pytest.mark.asyncio
@patch("backend.nodes.agents.summarizer.SummarizerService")
async def test_execute_with_valid_text(mock_service_class, node: SummarizerNode):
    # Setup mock
    mock_instance = mock_service_class.return_value
    mock_instance.summarize = AsyncMock(return_value="This is a short summary.")

    ctx = ExecutionContext(node_id=node.node_id, workflow_id="test-workflow-1", inputs={"text": "This is a long document text that needs to be summarized."}, config={"style": "short"})
    
    result = await node.execute(ctx)
    
    assert result.status.value == "success"
    assert result.outputs["summary"] == "This is a short summary."
    mock_service_class.assert_called_once()
    mock_instance.summarize.assert_called_once_with(text="This is a long document text that needs to be summarized.", style="short")


@pytest.mark.asyncio
async def test_execute_fails_with_empty_text(node: SummarizerNode):
    ctx = ExecutionContext(node_id=node.node_id, workflow_id="test-workflow-1", inputs={"text": "   "}, config={"style": "short"})
    
    result = await node.execute(ctx)
    
    assert result.status.value == "failure"
    assert "No valid text provided" in result.error
