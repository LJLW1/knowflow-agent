from fastapi.testclient import TestClient

from knowflow.api.app import create_app
from knowflow.config import Settings
from knowflow.rag.llm import FakeLLM


def make_settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'knowflow.db'}",
        chroma_path=str(tmp_path / "chroma"),
        upload_path=str(tmp_path / "uploads"),
        report_path=str(tmp_path / "reports"),
        embedding_backend="hash",
        vector_backend="memory",
    )


def test_health_and_document_upload(tmp_path) -> None:
    with TestClient(create_app(make_settings(tmp_path), llm=FakeLLM())) as client:
        health = client.get("/healthz")
        upload = client.post(
            "/api/v1/documents",
            data={"project_id": "demo"},
            files={"file": ("runbook.txt", b"Run tests before release.", "text/plain")},
        )
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert upload.status_code == 201
    assert upload.json()["chunks_indexed"] == 1


def test_query_returns_citations_and_trace_header(tmp_path) -> None:
    with TestClient(create_app(make_settings(tmp_path), llm=FakeLLM())) as client:
        client.post(
            "/api/v1/documents",
            data={"project_id": "demo"},
            files={"file": ("runbook.txt", b"Run tests before release.", "text/plain")},
        )
        response = client.post(
            "/api/v1/query",
            json={"project_id": "demo", "question": "What is required before release?"},
        )
    assert response.status_code == 200
    assert response.json()["citations"]
    assert response.headers["x-trace-id"] == response.json()["trace_id"]


def test_query_without_key_is_an_explicit_service_error(tmp_path) -> None:
    settings = make_settings(tmp_path)
    settings.openai_api_key = None
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/query",
            json={"project_id": "demo", "question": "What is required?"},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_NOT_CONFIGURED"


def test_document_endpoint_rejects_traversal_filename(tmp_path) -> None:
    with TestClient(create_app(make_settings(tmp_path), llm=FakeLLM())) as client:
        response = client.post(
            "/api/v1/documents",
            data={"project_id": "demo"},
            files={"file": ("../secret.txt", b"secret", "text/plain")},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILENAME"
