"""
End-to-end test for the Document Upload node.

Run standalone (no server needed):
  python backend/test_document_upload_e2e.py

Or start the server first, then run with --api:
  uvicorn backend.main:app --reload
  python backend/test_document_upload_e2e.py --api
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

# Ensure the project root is on sys.path so imports like `backend.xxx` work
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def test_standalone():
    print("\n--- Standalone Test (no server needed) ---\n")

    from backend.sdk import ExecutionContext, NodeStatus
    from backend.nodes.ingestion.document_upload import DocumentUploadNode

    passed = 0
    failed = 0

    # Test 1: Execute with file input
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf = Path(tmpdir) / "hello.pdf"
        pdf.write_bytes(b"%PDF-1.4 mock content")

        node = DocumentUploadNode(node_id="test-1", config={})
        ctx = ExecutionContext(
            workflow_id="wf-1",
            node_id="test-1",
            inputs={
                "file": {
                    "filename": pdf.name,
                    "path": str(pdf),
                    "size_bytes": pdf.stat().st_size,
                }
            },
            config={},
        )

        result = asyncio.run(node.execute(ctx))
        ok = result.status == NodeStatus.SUCCESS
        if ok:
            print(f"  [PASS] Execute with file input -> {result.outputs['file_name']} ({result.outputs['size_bytes']} bytes)")
            passed += 1
        else:
            print(f"  [FAIL] Execute with file input -> {result.status} {result.error}")
            failed += 1

    # Test 2: Fails gracefully with no input
    node2 = DocumentUploadNode(node_id="test-2", config={})
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
        node3 = DocumentUploadNode(node_id="test-3", config={"allowed_extensions": [".pdf"]})
        ctx3 = ExecutionContext(
            workflow_id="wf-1", node_id="test-3",
            inputs={"file": {"filename": exe.name, "path": str(exe), "size_bytes": exe.stat().st_size}},
            config={"allowed_extensions": [".pdf"]},
        )
        result3 = asyncio.run(node3.execute(ctx3))
        if result3.status == NodeStatus.FAILURE and ".exe" in result3.error:
            print(f"  [PASS] Rejects disallowed extension -> '{result3.error}'")
            passed += 1
        else:
            print(f"  [FAIL] Rejects disallowed extension -> {result3.status} {result3.error}")
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
        if "document-upload" not in types:
            print("  [FAIL] document-upload node not found in registry")
            return False
        print(f"  [PASS] GET /api/nodes -> found document-upload (total: {data['total']} nodes)")
    except urllib.error.URLError:
        print(f"  [FAIL] Cannot reach server at {base_url} (start it with: uvicorn backend.main:app --reload)")
        return False

    # 2. Create a test file and upload it
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test-doc.pdf"
        test_file.write_bytes(b"%PDF-1.4 e2e test document")

        boundary = "----WebKitFormBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{test_file.name}"\r\n'
            f"Content-Type: application/pdf\r\n\r\n"
        ).encode() + test_file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()

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

        # 3. Execute workflow with the document-upload node
        payload = json.dumps({
            "id": "e2e-test",
            "nodes": [{"id": "n1", "type": "document-upload", "config": {"file_id": file_id}}],
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
                print(f"         file_name:  {out['file_name']}")
                print(f"         mime_type:  {out['mime_type']}")
                print(f"         size_bytes: {out['size_bytes']}")
                print(f"         document:   {json.dumps(out['document'])}")
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
