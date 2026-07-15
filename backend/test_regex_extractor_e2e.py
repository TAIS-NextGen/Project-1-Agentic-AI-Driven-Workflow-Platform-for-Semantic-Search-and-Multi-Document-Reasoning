"""
End-to-end test for the Regex Extractor node.

Run standalone (no server needed):
  python backend/test_regex_extractor_e2e.py

Or start the server first, then run with --api:
  uvicorn backend.main:app --reload
  python backend/test_regex_extractor_e2e.py --api
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
    from backend.nodes.extraction.regex_extractor import RegexExtractorNode

    passed = 0
    failed = 0

    # Test 1: Extract phone and email
    node1 = RegexExtractorNode(node_id="test-1", config={
        "template": "generic", "language": "fr",
    })
    ctx1 = ExecutionContext(
        workflow_id="wf-1", node_id="test-1",
        inputs={"text": "Tel: +216 21 123 456, Email: test@example.com"},
        config={"template": "generic", "language": "fr"},
    )
    result1 = asyncio.run(node1.execute(ctx1))
    if result1.status == NodeStatus.SUCCESS:
        print(f"  [PASS] Extract phone and email -> extracted {len(result1.outputs['extracted'])} categories")
        passed += 1
    else:
        print(f"  [FAIL] Extract phone and email -> {result1.error}")
        failed += 1

    # Test 2: Extract invoice fields (French template)
    node2 = RegexExtractorNode(node_id="test-2", config={
        "template": "invoice_fr", "language": "fr",
    })
    ctx2 = ExecutionContext(
        workflow_id="wf-1", node_id="test-2",
        inputs={"text": "Facture N° F2024-001\nDate: 15/03/2024\nFournisseur: Société ABC\nMontant TTC: 2500 DT\nTVA: 19%"},
        config={"template": "invoice_fr", "language": "fr"},
    )
    result2 = asyncio.run(node2.execute(ctx2))
    if result2.status == NodeStatus.SUCCESS:
        print(f"  [PASS] Invoice fields extracted -> stats: {result2.outputs['stats']}")
        passed += 1
    else:
        print(f"  [FAIL] Invoice fields extraction -> {result2.error}")
        failed += 1

    # Test 3: Missing fields reported
    node3 = RegexExtractorNode(node_id="test-3", config={
        "template": "invoice_fr", "language": "fr",
    })
    ctx3 = ExecutionContext(
        workflow_id="wf-1", node_id="test-3",
        inputs={"text": "Just some random text"},
        config={"template": "invoice_fr", "language": "fr"},
    )
    result3 = asyncio.run(node3.execute(ctx3))
    if result3.status == NodeStatus.SUCCESS and len(result3.outputs["missing"]) > 0:
        print(f"  [PASS] Missing fields reported -> {result3.outputs['missing']}")
        passed += 1
    else:
        print(f"  [FAIL] Missing fields -> {result3.status} {result3.error}")
        failed += 1

    # Test 4: Fails with no input
    node4 = RegexExtractorNode(node_id="test-4", config={})
    ctx4 = ExecutionContext(workflow_id="wf-1", node_id="test-4", inputs={}, config={})
    result4 = asyncio.run(node4.execute(ctx4))
    if result4.status == NodeStatus.FAILURE and "No text provided" in result4.error:
        print(f"  [PASS] Fails gracefully with no input")
        passed += 1
    else:
        print(f"  [FAIL] No input handling -> {result4.status} {result4.error}")
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
        if "regex-extractor" not in types:
            print("  [FAIL] regex-extractor node not found in registry")
            return False
        print(f"  [PASS] GET /api/nodes -> found regex-extractor (total: {data['total']} nodes)")
    except urllib.error.URLError:
        print(f"  [FAIL] Cannot reach server at {base_url}")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        txt_file = Path(tmpdir) / "sample-invoice.txt"
        txt_file.write_text(
            "Facture N° INV-2024-789\n"
            "Date: 12/06/2024\n"
            "Client: SARL Tech Solutions\n"
            "Montant TTC: 4500 DT\n"
            "TVA: 19%\n",
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
            "id": "e2e-test-regex",
            "nodes": [
                {
                    "id": "n1",
                    "type": "regex-extractor",
                    "config": {"file_id": file_id, "template": "invoice_fr", "language": "fr"},
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
                print(f"         extracted categories: {list(out['extracted'].keys())}")
                print(f"         matched patterns: {out['stats']['matched']}/{out['stats']['total_patterns']}")
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
