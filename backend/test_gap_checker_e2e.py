"""
End-to-end test for the Gap Checker node.

Run standalone (no server needed):
  python backend/test_gap_checker_e2e.py

Or start the server first, then run with --api:
  uvicorn backend.main:app --reload
  python backend/test_gap_checker_e2e.py --api
"""
import argparse
import asyncio
import json
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def _create_test_files(tmpdir: str) -> tuple[Path, Path]:
    dir_path = Path(tmpdir)
    complete = dir_path / "complete.txt"
    complete.write_text(
        "Facture N F2024-156\n"
        "Date: 12/06/2024\n"
        "Fournisseur: Societe ABC\n"
        "Client: Jean Dupont\n"
        "Montant TTC: 2500 DT\n"
        "TVA: 19%\n",
        encoding="utf-8",
    )

    partial = dir_path / "partial.txt"
    partial.write_text(
        "Date: 15/03/2024\n"
        "Just some random text\n"
        "No invoice number here\n",
        encoding="utf-8",
    )

    return complete, partial


def test_standalone():
    print("\n--- Standalone Test (no server needed) ---\n")

    from backend.sdk import ExecutionContext, NodeStatus
    from backend.nodes.checking.gap_checker import GapCheckerNode

    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        complete, partial = _create_test_files(tmpdir)

        node1 = GapCheckerNode(node_id="test-1", config={
            "template": "invoice_fr",
            "evaluation_mode": "deterministic_only",
        })
        ctx1 = ExecutionContext(
            workflow_id="wf-1", node_id="test-1",
            inputs={
                "document": {
                    "filename": complete.name,
                    "path": str(complete),
                    "size_bytes": complete.stat().st_size,
                }
            },
            config={"template": "invoice_fr", "evaluation_mode": "deterministic_only"},
        )
        result1 = asyncio.run(node1.execute(ctx1))
        if result1.status == NodeStatus.SUCCESS:
            score = result1.outputs["score"]
            print(f"  [PASS] Complete doc -> {score['percentage']}% ({score['matched']}/{score['total_fields']} fields)")
            passed += 1
        else:
            print(f"  [FAIL] Complete doc -> {result1.status} {result1.error}")
            failed += 1

        node2 = GapCheckerNode(node_id="test-2", config={
            "template": "invoice_fr",
            "evaluation_mode": "deterministic_only",
        })
        ctx2 = ExecutionContext(
            workflow_id="wf-1", node_id="test-2",
            inputs={
                "document": {
                    "filename": partial.name,
                    "path": str(partial),
                    "size_bytes": partial.stat().st_size,
                }
            },
            config={"template": "invoice_fr", "evaluation_mode": "deterministic_only"},
        )
        result2 = asyncio.run(node2.execute(ctx2))
        if result2.status == NodeStatus.SUCCESS:
            score = result2.outputs["score"]
            missing = result2.outputs["missing"]
            print(f"  [PASS] Partial doc -> {score['percentage']}%, missing: {missing}")
            passed += 1
        else:
            print(f"  [FAIL] Partial doc -> {result2.status} {result2.error}")
            failed += 1

        custom_checklist = json.dumps([
            {
                "key": "date_found",
                "label": "Date",
                "required": True,
                "severity": "CRITICAL",
                "pattern": "\\d{2}/\\d{2}/\\d{4}",
            },
            {
                "key": "reference",
                "label": "Reference",
                "required": True,
                "severity": "CRITICAL",
                "pattern": "F2024-\\d+",
            },
        ])
        node3 = GapCheckerNode(node_id="test-3", config={
            "custom_checklist": custom_checklist,
            "evaluation_mode": "deterministic_only",
        })
        ctx3 = ExecutionContext(
            workflow_id="wf-1", node_id="test-3",
            inputs={
                "document": {
                    "filename": complete.name,
                    "path": str(complete),
                    "size_bytes": complete.stat().st_size,
                }
            },
            config={"custom_checklist": custom_checklist, "evaluation_mode": "deterministic_only"},
        )
        result3 = asyncio.run(node3.execute(ctx3))
        if result3.status == NodeStatus.SUCCESS and result3.outputs["score"]["percentage"] == 100.0:
            print(f"  [PASS] Custom checklist -> {result3.outputs['score']['percentage']}%")
            passed += 1
        else:
            print(f"  [FAIL] Custom checklist -> {result3.status}")
            failed += 1

        node4 = GapCheckerNode(node_id="test-4", config={})
        ctx4 = ExecutionContext(workflow_id="wf-1", node_id="test-4", inputs={}, config={})
        result4 = asyncio.run(node4.execute(ctx4))
        if result4.status == NodeStatus.FAILURE and "No file provided" in result4.error:
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
        if "gap-checker" not in types:
            print("  [FAIL] gap-checker node not found in registry")
            return False
        print(f"  [PASS] GET /api/nodes -> found gap-checker (total: {data['total']} nodes)")
    except urllib.error.URLError:
        print(f"  [FAIL] Cannot reach server at {base_url}")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        txt_file = Path(tmpdir) / "invoice.txt"
        txt_file.write_text(
            "Facture N INV-2024-789\n"
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
            "id": "e2e-test-gap",
            "nodes": [
                {
                    "id": "n1",
                    "type": "gap-checker",
                    "config": {
                        "file_id": file_id,
                        "template": "invoice_fr",
                        "evaluation_mode": "deterministic_only",
                    },
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
                print(f"         score: {out['score']['percentage']}%")
                print(f"         matched: {out['score']['matched']}/{out['score']['total_fields']}")
                print(f"         missing critical: {out['missing']}")
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
