from __future__ import annotations

from pathlib import Path

import pytest

from backend.nodes.preprocessing.contrast_enhancer import ContrastEnhancerNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def low_contrast_image(tmp_path: Path) -> Path:
    from PIL import Image

    image = Image.new("L", (120, 80), color=118)
    for x in range(30, 90):
        for y in range(20, 60):
            image.putpixel((x, y), 132)
    path = tmp_path / "low-contrast.png"
    image.convert("RGB").save(path)
    return path


def test_node_definition():
    node = ContrastEnhancerNode(node_id="enhance-1", config={})
    assert node.type == "contrast-enhancer"
    assert node.inputs[0].name == "image"
    assert {port.name for port in node.outputs} == {"image", "metadata"}


@pytest.mark.asyncio
async def test_enhances_image_and_writes_output(low_contrast_image: Path, tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    node = ContrastEnhancerNode(
        node_id="enhance-1",
        config={"contrast": 1.8, "brightness": 1.05, "sharpness": 1.2, "auto_contrast": True},
    )
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="enhance-1",
        inputs={
            "image": {
                "filename": low_contrast_image.name,
                "path": str(low_contrast_image),
                "size_bytes": low_contrast_image.stat().st_size,
            }
        },
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, result.error
    output_path = Path(result.outputs["image"]["path"])
    assert output_path.exists()
    assert output_path.suffix == ".png"
    assert result.outputs["metadata"]["contrast"] == 1.8
    assert result.outputs["metadata"]["auto_contrast"] is True

    from PIL import Image, ImageStat

    with Image.open(low_contrast_image) as before, Image.open(output_path) as after:
        before_stddev = ImageStat.Stat(before.convert("L")).stddev[0]
        after_stddev = ImageStat.Stat(after.convert("L")).stddev[0]
    assert after_stddev > before_stddev


@pytest.mark.asyncio
async def test_fails_without_image():
    node = ContrastEnhancerNode(node_id="enhance-1", config={})
    ctx = ExecutionContext(workflow_id="wf-1", node_id="enhance-1", inputs={}, config={}, services={})

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No image provided" in (result.error or "")
