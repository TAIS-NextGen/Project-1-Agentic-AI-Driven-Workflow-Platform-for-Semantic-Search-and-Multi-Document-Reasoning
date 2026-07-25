"""
End-to-end test for the Document Structure Analyzer node (Unstructured engine).

Run standalone (no server needed):
  python backend/test_structure_analyzer_e2e.py

Or start the server first, then run with --api:
  uvicorn backend.main:app --reload
  python backend/test_structure_analyzer_e2e.py --api
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


def _create_test_image(path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("arial.ttf", 32)
        body_font = ImageFont.truetype("arial.ttf", 18)
        small_font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.text((50, 20), "CONFIDENTIAL", fill="gray", font=small_font)
    draw.text((50, 60), "Rapport Annuel", fill="black", font=title_font)
    draw.text((50, 130), "Introduction", fill="black", font=body_font)
    draw.text((50, 170), "Ce rapport presente les resultats de l annee 2024.", fill="black", font=body_font)
    draw.text((50, 220), "Resultats Financiers", fill="black", font=body_font)
    draw.text((50, 260), "Chiffre d affaires: 2 500 000 DT. Benefice net: 450 000 DT.", fill="black", font=body_font)
    draw.text((50, 320), "Conclusion", fill="black", font=body_font)
    draw.text((50, 360), "L entreprise continue sa croissance avec de nouveaux projets prevus pour 2025.", fill="black", font=body_font)
    draw.text((50, 570), "Page 1/1 - CONFIDENTIEL", fill="gray", font=small_font)

    img.save(path)


def test_standalone():
    print("\n--- Standalone Test (no server needed) ---\n")

    from backend.sdk import ExecutionContext, NodeStatus
    from backend.nodes.structure.structure_analyzer import DocumentStructureAnalyzerNode

    passed = 0
    failed = 0

    # Test 1: Analyze image document
    with tempfile.TemporaryDirectory() as tmpdir:
        img = Path(tmpdir) / "report.png"
        _create_test_image(img)

        node = DocumentStructureAnalyzerNode(node_id="test-1", config={})
        ctx = ExecutionContext(
            workflow_id="wf-1", node_id="test-1",
            inputs={
                "document": {
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
            layout = result.outputs["structure"][0]["layout"]
            layout_types = {r["type"] for r in layout}
            print(f"  [PASS] Analyze image -> {len(layout)} regions detected: {layout_types}")
            passed += 1
        else:
            print(f"  [FAIL] Analyze image -> {result.status} {result.error}")
            failed += 1

    # Test 2: Fails gracefully with no input
    node2 = DocumentStructureAnalyzerNode(node_id="test-2", config={})
    ctx2 = ExecutionContext(workflow_id="wf-1", node_id="test-2", inputs={}, config={})
    result2 = asyncio.run(node2.execute(ctx2))
    if result2.status == NodeStatus.FAILURE and "No file provided" in result2.error:
        print(f"  [PASS] Fails gracefully with no input")
        passed += 1
    else:
        print(f"  [FAIL] Fails gracefully -> {result2.status} {result2.error}")
        failed += 1

    # Test 3: Rejects disallowed extension
    with tempfile.TemporaryDirectory() as tmpdir:
        exe = Path(tmpdir) / "virus.exe"
        exe.write_bytes(b"fake exe")
        node3 = DocumentStructureAnalyzerNode(node_id="test-3", config={"allowed_extensions": [".pdf"]})
        ctx3 = ExecutionContext(
            workflow_id="wf-1", node_id="test-3",
            inputs={"document": {"filename": exe.name, "path": str(exe), "size_bytes": exe.stat().st_size}},
            config={"allowed_extensions": [".pdf"]},
        )
        result3 = asyncio.run(node3.execute(ctx3))
        if result3.status == NodeStatus.FAILURE and ".exe" in result3.error:
            print(f"  [PASS] Rejects disallowed extension")
            passed += 1
        else:
            print(f"  [FAIL] Extension rejection -> {result3.status} {result3.error}")
            failed += 1

    # Test 4: Summary output present
    with tempfile.TemporaryDirectory() as tmpdir:
        img = Path(tmpdir) / "doc.png"
        _create_test_image(img)
        node4 = DocumentStructureAnalyzerNode(node_id="test-4", config={})
        ctx4 = ExecutionContext(
            workflow_id="wf-1", node_id="test-4",
            inputs={"document": {"filename": img.name, "path": str(img), "size_bytes": img.stat().st_size}},
            config={},
        )
        result4 = asyncio.run(node4.execute(ctx4))
        if result4.status == NodeStatus.SUCCESS and "elements_by_type" in result4.outputs["summary"]:
            print(f"  [PASS] Summary stats -> {result4.outputs['summary']['elements_by_type']}")
            passed += 1
        else:
            print(f"  [FAIL] Summary -> {result4.status}")
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
        if "document-structure-analyzer" not in types:
            print("  [FAIL] document-structure-analyzer node not found in registry")
            return False
        print(f"  [PASS] GET /api/nodes -> found document-structure-analyzer (total: {data['total']} nodes)")
    except urllib.error.URLError:
        print(f"  [FAIL] Cannot reach server at {base_url}")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        test_img = Path(tmpdir) / "report.png"
        _create_test_image(test_img)

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

        payload = json.dumps({
            "id": "e2e-test-structure",
            "nodes": [
                {
                    "id": "n1",
                    "type": "document-structure-analyzer",
                    "config": {"file_id": file_id},
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
                layout_regions = out["structure"][0]["layout"]
                print(f"  [PASS] Workflow executed successfully")
                print(f"         regions detected: {len(layout_regions)}")
                print(f"         layout types: {set(r['type'] for r in layout_regions)}")
                print(f"         summary: {out['summary']['elements_by_type']}")
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
