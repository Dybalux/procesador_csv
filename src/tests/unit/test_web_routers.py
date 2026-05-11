"""Tests básicos para routers FastAPI."""

from __future__ import annotations

from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(postgres_container: Any, file_storage: Any) -> tuple[TestClient, Any]:
    """Crea app FastAPI con PostgreSQL real."""
    import sys

    # Limpiar módulos para forzar reimport con nueva DB URL
    for key in list(sys.modules.keys()):
        if key.startswith("infrastructure.web") or key.startswith("infrastructure.db"):
            del sys.modules[key]

    from infrastructure.storage.local_file_storage import LocalFileStorage
    from infrastructure.web.dependencies import get_file_storage
    from infrastructure.web.main import create_app

    app = create_app()
    app.dependency_overrides[get_file_storage] = lambda: file_storage

    with TestClient(app) as c:
        yield c, file_storage


class TestUploadRouter:
    def test_upload_valid_csv_returns_202(self, client: tuple[TestClient, Any]) -> None:
        c, _ = client
        response = c.post(
            "/api/v1/upload",
            files={
                "file": (
                    "test.csv",
                    BytesIO(b"email,website,date\na@b.com,http://c.com,2023-01-01\n"),
                ),
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        UUID(data["task_id"])  # valida formato UUID

    def test_upload_non_csv_returns_400(self, client: tuple[TestClient, Any]) -> None:
        c, _ = client
        response = c.post(
            "/api/v1/upload",
            files={"file": ("test.txt", BytesIO(b"hello"))},
        )
        assert response.status_code == 400

    def test_upload_empty_file_returns_400(self, client: tuple[TestClient, Any]) -> None:
        c, _ = client
        response = c.post(
            "/api/v1/upload",
            files={"file": ("test.csv", BytesIO(b""))},
        )
        assert response.status_code == 400

    def test_upload_too_large_returns_413(self, client: tuple[TestClient, Any]) -> None:
        c, _ = client
        response = c.post(
            "/api/v1/upload",
            files={"file": ("test.csv", BytesIO(b"x" * (104_857_600 + 1)))},
        )
        assert response.status_code == 413


class TestTasksRouter:
    def test_get_existing_task_returns_200(self, client: tuple[TestClient, Any]) -> None:
        c, _ = client
        from uuid import UUID
        
        # Primero crear una tarea vía upload
        upload_response = c.post(
            "/api/v1/upload",
            files={
                "file": (
                    "test.csv",
                    BytesIO(b"Email,Website,Subscription Date\nalice@example.com,https://example.com,2024-01-15\n"),
                ),
            },
        )
        assert upload_response.status_code == 202
        task_id = upload_response.json()["task_id"]
        
        # Ahora consultar la tarea
        response = c.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PENDING"
        assert data["processed_rows"] == 0
        assert data["total_rows"] == 1

    def test_get_missing_task_returns_404(self, client: tuple[TestClient, Any]) -> None:
        c, _ = client
        from uuid import uuid4
        response = c.get(f"/api/v1/tasks/{uuid4()}")
        assert response.status_code == 404
