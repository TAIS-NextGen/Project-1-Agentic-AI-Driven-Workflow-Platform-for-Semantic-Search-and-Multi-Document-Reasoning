import pytest
from unittest.mock import patch, MagicMock

from backend.sdk import ExecutionContext
from backend.nodes.extraction.barcode_reader import BarcodeReaderNode


@pytest.fixture
def node():
    return BarcodeReaderNode(node_id="test-barcode-1")


def test_node_definition(node: BarcodeReaderNode):
    assert node.type == "barcode-reader"
    assert node.name == "Barcode & QR Reader"
    assert node.category == "extraction"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "image"
    assert len(node.outputs) == 3
    assert node.outputs[0].name == "barcodes_data"
    assert node.outputs[1].name == "annotated_image"
    assert node.outputs[2].name == "text"


@pytest.mark.asyncio
@patch("backend.nodes.extraction.barcode_reader.BarcodeReaderService")
async def test_execute_with_valid_image(mock_service_class, node: BarcodeReaderNode):
    mock_instance = mock_service_class.return_value
    
    mock_barcodes = [
        {"type": "QRCODE", "data": "https://example.com", "rect": {"left": 0, "top": 0, "width": 100, "height": 100}},
        {"type": "CODE128", "data": "123456789", "rect": {"left": 10, "top": 10, "width": 50, "height": 20}}
    ]
    mock_instance.detect_and_decode.return_value = (mock_barcodes, "/tmp/annotated.png")

    ctx = ExecutionContext(
        node_id=node.node_id, 
        workflow_id="test-wf",
        inputs={"image": "/tmp/test.png"},
        config={"draw_boxes": True}
    )
    
    result = await node.execute(ctx)
    
    assert result.status.value == "success"
    assert result.outputs["barcodes_data"] == mock_barcodes
    assert result.outputs["annotated_image"] == "/tmp/annotated.png"
    assert result.outputs["text"] == "https://example.com\n123456789"
    
    mock_instance.detect_and_decode.assert_called_once_with(image_path="/tmp/test.png", draw_boxes=True)


@pytest.mark.asyncio
async def test_execute_fails_with_empty_image(node: BarcodeReaderNode):
    ctx = ExecutionContext(
        node_id=node.node_id,
        workflow_id="test-wf",
        inputs={"image": ""},
        config={"draw_boxes": True}
    )
    
    result = await node.execute(ctx)
    
    assert result.status.value == "failure"
    assert "No valid image provided" in result.error
