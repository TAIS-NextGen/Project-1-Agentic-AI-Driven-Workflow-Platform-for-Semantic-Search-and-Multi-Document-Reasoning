from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import documents
from backend.main import app
from backend.sdk import NodeRegistry


def configure_temporary_storage(monkeypatch, tmp_path: Path) -> Path:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(documents, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(documents, "INDEX_PATH", upload_dir / ".documents-index.json")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.chdir(tmp_path)
    NodeRegistry().clear()
    return upload_dir


def test_local_upload_can_be_listed_downloaded_and_executed(monkeypatch, tmp_path: Path):
    configure_temporary_storage(monkeypatch, tmp_path)

    with TestClient(app) as client:
        uploaded = client.post(
            "/api/documents/upload",
            files={"file": ("notes.txt", b"hello workflow", "text/plain")},
        )
        assert uploaded.status_code == 200, uploaded.text
        record = uploaded.json()
        assert record["filename"] == "notes.txt"
        assert record["source"] == "local"

        listing = client.get("/api/documents")
        assert listing.status_code == 200
        assert listing.json()["total"] == 1
        assert listing.json()["documents"][0]["file_id"] == record["file_id"]

        execution = client.post(
            "/api/workflows/execute",
            json={
                "id": "upload-workflow",
                "nodes": [
                    {
                        "id": "input-1",
                        "type": "document-upload",
                        "config": {
                            "file_id": record["file_id"],
                            "allowed_extensions": [".txt"],
                            "max_file_size_mb": 50,
                        },
                    }
                ],
                "edges": [],
                "validate_mode": "relaxed",
            },
        )
        assert execution.status_code == 200, execution.text
        payload = execution.json()
        assert payload["status"] == "completed"
        assert payload["succeeded"] == 1
        assert payload["results"]["input-1"]["outputs"]["file_name"] == "notes.txt"

        downloaded = client.get(f"/api/documents/{record['file_id']}/download")
        assert downloaded.status_code == 200
        assert downloaded.content == b"hello workflow"

        deleted = client.delete(f"/api/documents/{record['file_id']}")
        assert deleted.status_code == 200
        assert client.get("/api/documents").json()["total"] == 0


def test_batch_upload_reports_invalid_files_without_losing_valid_files(monkeypatch, tmp_path: Path):
    configure_temporary_storage(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/documents/upload/batch",
            files=[
                ("files", ("valid.md", b"# title", "text/markdown")),
                ("files", ("invalid.exe", b"not allowed", "application/octet-stream")),
            ],
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["uploaded"] == 1
    assert payload["failed"] == 1
    assert payload["documents"][0]["filename"] == "valid.md"
    assert payload["errors"][0]["filename"] == "invalid.exe"



def test_folder_batch_upload_preserves_relative_paths(monkeypatch, tmp_path: Path):
    configure_temporary_storage(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/documents/upload/batch",
            files=[
                ("files", ("budget.txt", b"finance budget", "text/plain")),
                ("files", ("clinic.txt", b"health clinic", "text/plain")),
            ],
            data={"relative_paths": ["corpus/finance/budget.txt", "corpus/health/clinic.txt"]},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["uploaded"] == 2
    assert [item["relative_path"] for item in payload["documents"]] == [
        "corpus/finance/budget.txt",
        "corpus/health/clinic.txt",
    ]
    assert all(item["source"] == "local-folder" for item in payload["documents"])

def test_private_cloud_urls_are_rejected(monkeypatch, tmp_path: Path):
    configure_temporary_storage(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/documents/import-url",
            json={"url": "http://127.0.0.1/private.pdf"},
        )

    assert response.status_code == 400
    assert "Private or local" in response.json()["detail"]


def test_public_cloud_url_is_downloaded_into_the_library(monkeypatch, tmp_path: Path):
    configure_temporary_storage(monkeypatch, tmp_path)

    class FakeResponse:
        headers = {
            "content-type": "application/pdf",
            "content-length": "13",
        }
        url = "https://cdn.example.test/report.pdf"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"%PDF-test-data"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def stream(self, method: str, url: str):
            assert method == "GET"
            assert url == "https://files.example.test/report.pdf"
            return FakeResponse()

    monkeypatch.setattr(documents, "_assert_public_http_url", lambda _url: None)
    monkeypatch.setattr(documents.httpx, "AsyncClient", FakeClient)

    with TestClient(app) as client:
        response = client.post(
            "/api/documents/import-url",
            json={"url": "https://files.example.test/report.pdf"},
        )
        listing = client.get("/api/documents")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"] == "report.pdf"
    assert payload["source"] == "cloud-url"
    assert listing.json()["total"] == 1
    assert listing.json()["documents"][0]["file_id"] == payload["file_id"]
