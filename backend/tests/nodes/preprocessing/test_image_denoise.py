from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.preprocessing.image_denoise import ImageDenoiseNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return ImageDenoiseNode(node_id="test-denoise-1", config={})


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    from PIL import Image

    img = Image.new("RGB", (120, 120), color=(20, 20, 20))
    for x in range(0, 120, 20):
        for y in range(0, 120, 20):
            img.putpixel((x, y), (255, 255, 255))
    path = tmp_path / "noise.png"
    img.save(path)
    return path


def test_node_definition(node: ImageDenoiseNode):
    assert node.type == "image-denoise"
    assert node.name == "Image Denoise"
    assert node.category == "preprocessing"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "image"
    assert len(node.outputs) == 2
    assert node.outputs[0].name == "image"
    assert node.outputs[1].name == "metadata"


@pytest.mark.asyncio
async def test_execute_with_image(node: ImageDenoiseNode, sample_image: Path):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-denoise-1",
        inputs={
            "image": {
                "filename": sample_image.name,
                "path": str(sample_image),
                "size_bytes": sample_image.stat().st_size,
            }
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    assert "image" in result.outputs
    assert "metadata" in result.outputs
    assert result.outputs["metadata"]["filename"] == sample_image.name
    assert result.outputs["metadata"]["denoise_method"] == "pil-median"
