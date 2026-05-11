"""Tests básicos para routers FastAPI."""

from __future__ import annotations

from io import BytesIO
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from domain.entities import ProcessingTask, TaskStatus
from tests.unit.fakes import FakeFileStorage, FakeTaskRepository


def _make_app():
    import os
    import sys

    # Force reimport of infrastructure modules with SQLite config
    for key in list(sys.modules.keys()):
        if (
            key.startswith("infrastructure")
            or key.startswith("api")
            or key.startswith("application")
        ):
            del sys.modules[key]

    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"

    # Import in correct order to ensure dependencies are loaded
    from infrastructure.db import connection  # noqa: F401
    from infrastructure.web.dependencies import get_file_storage, get_task_repo
    from infrastructure.web.main import create_app

    app = create_app()
    return app, get_task_repo, get_file_storage


@pytest.fixture
def client():
    app, get_task_repo, get_file_storage = _make_app()
    task_repo = FakeTaskRepository()
    file_storage = FakeFileStorage()
    app.dependency_overrides[get_task_repo] = lambda: task_repo
    app.dependency_overrides[get_file_storage] = lambda: file_storage
    with TestClient(app) as c:
        yield c, task_repo, file_storage


class TestUploadRouter:
    def test_upload_valid_csv_returns_202(self, client) -> None:
        c, task_repo, _ = client
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
        task = task_repo.get(UUID(data["task_id"]))
        assert task is not None
        assert task.status == TaskStatus.PENDING

    def test_upload_non_csv_returns_400(self, client) -> None:
        c, _, _ = client
        response = c.post(
            "/api/v1/upload",
            files={"file": ("test.txt", BytesIO(b"hello"))},
        )
        assert response.status_code == 400

    def test_upload_empty_file_returns_400(self, client) -> None:
        c, _, _ = client
        response = c.post(
            "/api/v1/upload",
            files={"file": ("test.csv", BytesIO(b""))},
        )
        assert response.status_code == 400

    def test_upload_too_large_returns_413(self, client) -> None:
        c, _, _ = client
        response = c.post(
            "/api/v1/upload",
            files={"file": ("test.csv", BytesIO(b"x" * (104_857_600 + 1)))},
        )
        assert response.status_code == 413


class TestTasksRouter:
    def test_get_existing_task_returns_200(self, client) -> None:
        c, task_repo, _ = client
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PROCESSING,
            total_rows=100,
            processed_rows=50,
        )
        task_repo.save(task)
        response = c.get(f"/api/v1/tasks/{task.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PROCESSING"
        assert data["processed_rows"] == 50
        assert data["total_rows"] == 100

    def test_get_missing_task_returns_404(self, client) -> None:
        c, _, _ = client
        response = c.get(f"/api/v1/tasks/{uuid4()}")
        assert response.status_code == 404
