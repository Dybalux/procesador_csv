"""Tests end-to-end para la API REST.

Usan FastAPI TestClient con dependencias reales (SQLAlchemy repos +
LocalFileStorage) sobre PostgreSQL via testcontainers.
"""

from __future__ import annotations

from io import BytesIO
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def e2e_client(postgres_container: Any, file_storage: Any) -> TestClient:
    """Crea app FastAPI con PostgreSQL real y storage temporal."""
    import sys

    # Limpiar módulos para forzar reimport con nueva DB URL
    for key in list(sys.modules.keys()):
        if key.startswith("infrastructure.web") or key.startswith(
            "infrastructure.db"
        ):
            del sys.modules[key]

    from infrastructure.storage.local_file_storage import LocalFileStorage
    from infrastructure.web.dependencies import get_file_storage
    from infrastructure.web.main import create_app

    app = create_app()
    app.dependency_overrides[get_file_storage] = lambda: file_storage

    with TestClient(app) as client:
        yield client


class TestUploadEndpoint:
    def test_upload_valid_csv_returns_202(self, e2e_client: TestClient) -> None:
        response = e2e_client.post(
            "/api/v1/upload",
            files={
                "file": (
                    "customers.csv",
                    BytesIO(
                        b"Email,Subscription Date,Website\n"
                        b"alice@example.com,2024-01-15,https://example.com\n"
                    ),
                ),
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        UUID(data["task_id"])  # valida formato UUID

    def test_upload_invalid_extension_returns_400(self, e2e_client: TestClient) -> None:
        response = e2e_client.post(
            "/api/v1/upload",
            files={"file": ("report.txt", BytesIO(b"some content"))},
        )
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    def test_upload_empty_file_returns_400(self, e2e_client: TestClient) -> None:
        response = e2e_client.post(
            "/api/v1/upload",
            files={"file": ("empty.csv", BytesIO(b""))},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_upload_too_large_returns_413(self, e2e_client: TestClient) -> None:
        response = e2e_client.post(
            "/api/v1/upload",
            files={
                "file": ("huge.csv", BytesIO(b"x" * (104_857_600 + 1))),
            },
        )
        assert response.status_code == 413


class TestTasksEndpoint:
    def test_get_existing_task_returns_200(self, e2e_client: TestClient) -> None:
        upload_resp = e2e_client.post(
            "/api/v1/upload",
            files={
                "file": (
                    "customers.csv",
                    BytesIO(
                        b"Email,Subscription Date,Website\n"
                        b"bob@example.com,2024-02-20,https://bob.dev\n"
                    ),
                ),
            },
        )
        assert upload_resp.status_code == 202
        task_id = upload_resp.json()["task_id"]

        response = e2e_client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PENDING"
        assert data["processed_rows"] == 0

    def test_get_missing_task_returns_404(self, e2e_client: TestClient) -> None:
        response = e2e_client.get(f"/api/v1/tasks/{uuid4()}")
        assert response.status_code == 404
