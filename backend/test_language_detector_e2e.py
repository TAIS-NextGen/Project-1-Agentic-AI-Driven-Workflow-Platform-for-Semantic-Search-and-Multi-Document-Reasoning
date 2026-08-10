"""
End-to-end test for the Language Detector node.

Run standalone (no server needed):
  python backend/test_language_detector_e2e.py

Or start the server first, then run with --api:
  uvicorn backend.main:app --reload
  python backend/test_language_detector_e2e.py --api
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


def test_standalone():
    print("\n--- Standalone Test (no server needed) ---\n")

    from backend.sdk import ExecutionContext, NodeStatus
    from backend.nodes.extraction.language_detector import LanguageDetectorNode

    passed = 0
    failed = 0

    # Test 1: Simple English text
    node1 = LanguageDetectorNode(node_id="test-1", config={})
    ctx1 = ExecutionContext(
        workflow_id="wf-1", node_id="test-1",
        inputs={"text": "This is a simple english text to test standalone mode."},
        config={},
    )
    result1 = asyncio.run(node1.execute(ctx1))
    if result1.status == NodeStatus.SUCCESS:
        print(f"  [PASS] English text detection -> {result1.outputs['languages_str']}")
        passed += 1
    else:
        print(f"  [FAIL] English text detection -> {result1.error}")
        failed += 1

    # Test 2: Paragraph mode for multi-language text
    node2 = LanguageDetectorNode(node_id="test-2", config={"detection_mode": "paragraph"})
    ctx2 = ExecutionContext(
        workflow_id="wf-1", node_id="test-2",
        inputs={
            "text": "Bonjour, c'est un paragraphe en français.\n\n"
                    "Hello, this is a paragraph in English.\n\n"
                    "Guten Tag, das ist ein Absatz in Deutsch."
        },
        config={"detection_mode": "paragraph"},
    )
    result2 = asyncio.run(node2.execute(ctx2))
    if result2.status == NodeStatus.SUCCESS:
        print(f"  [PASS] Paragraph mode multi-language -> {result2.outputs['languages_str']}")
        passed += 1
    else:
        print(f"  [FAIL] Paragraph mode multi-language -> {result2.error}")
        failed += 1

    print(f"\nResults: {passed} passed, {failed} failed\n")
    return failed == 0


def test_via_api(base_url="http://localhost:8000"):
    print(f"\n--- API Test (server at {base_url}) ---\n")

    try:
        req = urllib.request.Request(f"{base_url}/api/nodes")
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        types = [n["type"] for n in data["nodes"]]
        if "language-detector" not in types:
            print("  [FAIL] language-detector node not found in registry")
            return False
        print(f"  [PASS] GET /api/nodes -> found language-detector (total: {data['total']} nodes)")
    except urllib.error.URLError:
        print(f"  [FAIL] Cannot reach server at {base_url}")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        txt_file = Path(tmpdir) / "sample-multilang.txt"
        txt_file.write_text(
            "Ceci est du français.\n\n"
            "This is English.\n\n"
            "Esto es español.\n",
            encoding="utf-8",
        )

        boundary = "----WebKitFormBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{txt_file.name}"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode() + txt_file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()

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

        payload = json.dumps({
            "id": "e2e-test-lang",
            "nodes": [
                {
                    "id": "n1",
                    "type": "language-detector",
                    "config": {"file_id": file_id, "detection_mode": "paragraph", "min_probability": 0.1},
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
                print(f"  [PASS] Workflow executed successfully")
                print(f"         detected languages list: {out['languages']}")
                print(f"         detected languages string: {out['languages_str']}")
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
