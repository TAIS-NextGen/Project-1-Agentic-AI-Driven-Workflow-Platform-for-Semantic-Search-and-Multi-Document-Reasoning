from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from backend.nodes.preprocessing.orientation_detector import OrientationDetectorNode
from backend.sdk import ExecutionContext, NodeStatus


@pytest.fixture
def node():
    return OrientationDetectorNode(node_id="test-orient-1", config={})


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    path = tmp_path / "test_page.png"
    img.save(path)
    return path


@pytest.fixture
def upload_dir(monkeypatch, tmp_path: Path) -> Path:
    d = tmp_path / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(d))
    return d


def test_node_definition(node: OrientationDetectorNode):
    assert node.type == "orientation-detector"
    assert node.name == "Orientation Detector"
    assert node.category == "preprocessing"
    assert len(node.inputs) == 1
    assert node.inputs[0].name == "image"
    assert node.inputs[0].label == "Image/page"
    assert len(node.outputs) == 2
    assert node.outputs[0].name == "image"
    assert node.outputs[0].label == "Reoriented page"
    assert node.outputs[1].name == "metadata"
    assert len(node.config_fields) == 3


@pytest.mark.asyncio
async def test_execute_with_image(node: OrientationDetectorNode, sample_image: Path):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-orient-1",
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
    assert result.outputs["metadata"]["detected_angle"] == 0
    assert result.outputs["metadata"]["rotation_applied"] is False


@pytest.mark.asyncio
async def test_execute_with_file_id(sample_image: Path, upload_dir: Path):
    stored = upload_dir / sample_image.name
    shutil.copy2(sample_image, stored)
    file_id = stored.stem

    node_with_config = OrientationDetectorNode(
        node_id="test-orient-1", config={"file_id": file_id}
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-orient-1",
        inputs={},
        config={"file_id": file_id},
        services={},
    )

    result = await node_with_config.execute(ctx)

    assert result.status == NodeStatus.SUCCESS, f"Expected success, got: {result.error}"
    assert "image" in result.outputs
    assert result.outputs["metadata"]["filename"] == sample_image.name


@pytest.mark.asyncio
async def test_execute_fails_with_no_input(node: OrientationDetectorNode):
    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-orient-1",
        inputs={},
        config={},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "No image provided" in result.error


@pytest.mark.asyncio
async def test_execute_fails_for_disallowed_extension(tmp_path: Path):
    exe_file = tmp_path / "script.exe"
    exe_file.write_bytes(b"fake exe")

    node = OrientationDetectorNode(
        node_id="test-orient-1",
        config={"allowed_extensions": [".png", ".jpg"]},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-orient-1",
        inputs={
            "image": {
                "filename": exe_file.name,
                "path": str(exe_file),
                "size_bytes": exe_file.stat().st_size,
            }
        },
        config={"allowed_extensions": [".png", ".jpg"]},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert ".exe" in result.error


@pytest.mark.asyncio
async def test_execute_fails_for_oversized_file(sample_image: Path):
    node = OrientationDetectorNode(
        node_id="test-orient-1",
        config={"max_file_size_mb": 1},
    )

    ctx = ExecutionContext(
        workflow_id="wf-1",
        node_id="test-orient-1",
        inputs={
            "image": {
                "filename": sample_image.name,
                "path": str(sample_image),
                "size_bytes": 10 * 1024 * 1024,
            }
        },
        config={"max_file_size_mb": 1},
        services={},
    )

    result = await node.execute(ctx)

    assert result.status == NodeStatus.FAILURE
    assert "exceeds maximum" in result.error


def test_to_definition_returns_correct_shape(node: OrientationDetectorNode):
    definition = node.to_definition()
    assert definition["type"] == "orientation-detector"
    assert definition["name"] == "Orientation Detector"
    assert definition["category"] == "preprocessing"
    assert len(definition["inputs"]) == 1
    assert len(definition["outputs"]) == 2
    assert len(definition["config_fields"]) == 3
