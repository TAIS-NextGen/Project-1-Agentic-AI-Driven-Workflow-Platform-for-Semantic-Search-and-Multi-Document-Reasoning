"""
End-to-end test for the Handwriting OCR node.

Run standalone (no server needed):
  python backend/test_handwriting_ocr_e2e.py

Or start the server first, then run with --api:
  uvicorn backend.main:app --reload
  python backend/test_handwriting_ocr_e2e.py --api
"""
import argparse
import asyncio
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def _create_test_image(path: Path, text: str = "Hello World") -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    lines = text.split("\n")
    for i, line in enumerate(lines):
        draw.text((20, 40 + i * 50), line, fill="black", font=font)

    img.save(path)


def test_standalone():
    print("\n--- Standalone Test (no server needed) ---\n")

    from backend.sdk import ExecutionContext, NodeStatus
    from backend.nodes.extraction.handwriting_ocr import HandwritingOCRNode

    passed = 0
    failed = 0

    # Test 1: Execute with image input
    with tempfile.TemporaryDirectory() as tmpdir:
        img = Path(tmpdir) / "handwritten.png"
        _create_test_image(img, "Hello World\nTest OCR")

        node = HandwritingOCRNode(node_id="test-1", config={})
        ctx = ExecutionContext(
            workflow_id="wf-1",
            node_id="test-1",
            inputs={
                "image": {
                    "filename": img.name,
                    "path": str(img),
                    "size_bytes": img.stat().st_size,
                }
            },
            config={},
        )

        result = asyncio.run(node.execute(ctx))
        ok = result.status == NodeStatus.SUCCESS
        if ok:
            text_preview = result.outputs['text'][:50].encode('ascii', 'replace').decode('ascii')
            print(f"  [PASS] Execute with image input -> text='{text_preview}...' (confidence: {result.outputs['confidence']})")
            passed += 1
        else:
            print(f"  [FAIL] Execute with image input -> {result.status} {result.error}")
            failed += 1

    # Test 2: Fails gracefully with no input
    node2 = HandwritingOCRNode(node_id="test-2", config={})
    ctx2 = ExecutionContext(workflow_id="wf-1", node_id="test-2", inputs={}, config={})
    result2 = asyncio.run(node2.execute(ctx2))
    if result2.status == NodeStatus.FAILURE and "No file provided" in result2.error:
        print(f"  [PASS] Fails gracefully with no input -> '{result2.error}'")
        passed += 1
    else:
        print(f"  [FAIL] Fails gracefully with no input -> {result2.status} {result2.error}")
        failed += 1

    # Test 3: Fails for disallowed extension
    with tempfile.TemporaryDirectory() as tmpdir:
        exe = Path(tmpdir) / "virus.exe"
        exe.write_bytes(b"fake exe")
        node3 = HandwritingOCRNode(node_id="test-3", config={"allowed_extensions": [".png"]})
        ctx3 = ExecutionContext(
            workflow_id="wf-1", node_id="test-3",
            inputs={"image": {"filename": exe.name, "path": str(exe), "size_bytes": exe.stat().st_size}},
            config={"allowed_extensions": [".png"]},
        )
        result3 = asyncio.run(node3.execute(ctx3))
        if result3.status == NodeStatus.FAILURE and ".exe" in result3.error:
            print(f"  [PASS] Rejects disallowed extension -> '{result3.error}'")
            passed += 1
        else:
            print(f"  [FAIL] Rejects disallowed extension -> {result3.status} {result3.error}")
            failed += 1

    # Test 4: Works with Arabic config
    with tempfile.TemporaryDirectory() as tmpdir:
        img = Path(tmpdir) / "arabic.png"
        _create_test_image(img, "Hello World")

        node4 = HandwritingOCRNode(node_id="test-4", config={"language": "en"})
        ctx4 = ExecutionContext(
            workflow_id="wf-1", node_id="test-4",
            inputs={"image": {"filename": img.name, "path": str(img), "size_bytes": img.stat().st_size}},
            config={"language": "en"},
        )
        result4 = asyncio.run(node4.execute(ctx4))
        if result4.status == NodeStatus.SUCCESS:
            print(f"  [PASS] Works with English language -> confidence: {result4.outputs['confidence']}")
            passed += 1
        else:
            print(f"  [FAIL] Works with English language -> {result4.status} {result4.error}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed\n")
    return failed == 0


def test_via_api(base_url="http://localhost:8000"):
    print(f"\n--- API Test (server at {base_url}) ---\n")

    # 1. Check node is registered
    try:
        req = urllib.request.Request(f"{base_url}/api/nodes")
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        types = [n["type"] for n in data["nodes"]]
        if "handwriting-ocr" not in types:
            print("  [FAIL] handwriting-ocr node not found in registry")
            return False
        print(f"  [PASS] GET /api/nodes -> found handwriting-ocr (total: {data['total']} nodes)")
    except urllib.error.URLError:
        print(f"  [FAIL] Cannot reach server at {base_url} (start it with: uvicorn backend.main:app --reload)")
        return False

    # 2. Create a test image and upload it
    with tempfile.TemporaryDirectory() as tmpdir:
        test_img = Path(tmpdir) / "handwritten-test.png"
        _create_test_image(test_img, "Hello World\nHandwriting OCR Test")

        boundary = "----WebKitFormBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{test_img.name}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode() + test_img.read_bytes() + f"\r\n--{boundary}--\r\n".encode()

        try:
            req = urllib.request.Request(
                f"{base_url}/api/documents/upload",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            resp = urllib.request.urlopen(req)
            upload_data = json.loads(resp.read())
            file_id = upload_data["file_id"]
            print(f"  [PASS] POST /api/documents/upload -> file_id = {file_id}")
        except Exception as e:
            print(f"  [FAIL] Upload failed: {e}")
            return False

        # 3. Execute workflow with the handwriting-ocr node
        payload = json.dumps({
            "id": "e2e-test-hwocr",
            "nodes": [
                {
                    "id": "n1",
                    "type": "handwriting-ocr",
                    "config": {"file_id": file_id, "language": "en"},
                }
            ],
            "edges": [],
        }).encode()

        try:
            req = urllib.request.Request(
                f"{base_url}/api/workflows/execute",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req)
            result = json.loads(resp.read())
            nr = result["results"]["n1"]
            if nr["status"] == "success":
                out = nr["outputs"]
                text_preview = out['text'][:60].encode('ascii', 'replace').decode('ascii')
                print(f"  [PASS] Workflow executed successfully")
                print(f"         text:       {text_preview}...")
                print(f"         confidence: {out['confidence']}")
                print(f"         total_lines: {out['details']['total_lines']}")
            else:
                print(f"  [FAIL] Workflow node status = {nr['status']}: {nr.get('error')}")
                return False
        except Exception as e:
            print(f"  [FAIL] Workflow execution failed: {e}")
            return False

    print(f"\n  All API tests passed!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", action="store_true", help="Test via running API server")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the API")
    args = parser.parse_args()

    standalone_ok = test_standalone()

    if args.api:
        api_ok = test_via_api(args.url)
        all_ok = standalone_ok and api_ok
    else:
        api_ok = True
        all_ok = standalone_ok

    if all_ok:
        print("=== ALL TESTS PASSED ===")
        sys.exit(0)
    else:
        print("=== SOME TESTS FAILED ===")
        sys.exit(1)
