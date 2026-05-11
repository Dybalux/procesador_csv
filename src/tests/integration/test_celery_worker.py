"""Tests de integración para la tarea Celery process_csv_chunk.

Testean la lógica de la tarea directamente (sin broker ni worker)
usando SQLite en memoria y almacenamiento local en directorio temporal.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from domain.entities import ProcessingTask, TaskStatus


def _make_celery_task(tmp_path):
    """Reimporta módulos de infraestructura con SQLite en memoria."""
    for key in list(sys.modules.keys()):
        if key.startswith("infrastructure"):
            del sys.modules[key]
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from sqlalchemy.orm import sessionmaker

    from infrastructure.celery.tasks import process_csv_chunk
    from infrastructure.db.connection import Base, engine
    from infrastructure.storage.csv_mappers import CUSTOMERS_100_MAP

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Monkeypatch LocalFileStorage para usar tmp_path
    import infrastructure.celery.tasks as task_module

    original_local_storage = task_module.LocalFileStorage

    class TestLocalFileStorage(original_local_storage):
        def __init__(self, base_dir=None):
            super().__init__(base_dir=str(tmp_path))

    task_module.LocalFileStorage = TestLocalFileStorage

    return (
        process_csv_chunk,
        session,
        engine,
        original_local_storage,
        task_module,
        CUSTOMERS_100_MAP,
    )


@pytest.fixture
def celery_task_fixture(tmp_path):
    """Proporciona la tarea Celery y sesión de test."""
    process_csv_chunk, session, engine, orig, task_mod, csv_map = _make_celery_task(
        tmp_path
    )
    yield process_csv_chunk, session, engine, csv_map
    task_mod.LocalFileStorage = orig
    session.close()


class TestProcessCSVChunk:
    def test_processes_valid_rows(self, celery_task_fixture):
        process_csv_chunk, session, engine, _csv_map = celery_task_fixture

        import infrastructure.celery.tasks as task_module

        storage = task_module.LocalFileStorage()
        csv_content = (
            b"Email,Subscription Date,Website\n"
            b"alice@example.com,2024-01-15,https://example.com\n"
            b"bob@example.com,2024-02-20,https://bob.dev\n"
        )
        file_path = storage.save("valid.csv", csv_content)

        from infrastructure.db.repositories import SQLAlchemyTaskRepository

        task_repo = SQLAlchemyTaskRepository(session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PENDING,
            total_rows=2,
            file_path=file_path,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        task_repo.save(task)
        session.commit()

        result = process_csv_chunk.run(str(task.id), 0)

        assert result["valid_count"] == 2
        assert result["error_count"] == 0

        from sqlalchemy.orm import sessionmaker

        from infrastructure.db.repositories import (
            SQLAlchemyCustomerRepository,
            SQLAlchemyErrorRepository,
        )

        Session = sessionmaker(bind=engine)
        fresh_session = Session()
        customer_repo = SQLAlchemyCustomerRepository(fresh_session, task_id=task.id)
        assert customer_repo.count_by_task(task.id) == 2

        error_repo = SQLAlchemyErrorRepository(fresh_session)
        assert len(error_repo.list_by_task(task.id)) == 0

        task_repo2 = SQLAlchemyTaskRepository(fresh_session)
        found_task = task_repo2.get(task.id)
        assert found_task is not None
        assert found_task.status == TaskStatus.COMPLETED
        fresh_session.close()

    def test_processes_invalid_rows(self, celery_task_fixture):
        process_csv_chunk, session, engine, _csv_map = celery_task_fixture

        import infrastructure.celery.tasks as task_module

        storage = task_module.LocalFileStorage()
        csv_content = (
            b"Email,Subscription Date,Website\n"
            b"invalid-email,2024-01-15,https://example.com\n"
            b"bob@example.com,not-a-date,https://bob.dev\n"
        )
        file_path = storage.save("invalid.csv", csv_content)

        from infrastructure.db.repositories import SQLAlchemyTaskRepository

        task_repo = SQLAlchemyTaskRepository(session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PENDING,
            total_rows=2,
            file_path=file_path,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        task_repo.save(task)
        session.commit()

        result = process_csv_chunk.run(str(task.id), 0)

        assert result["valid_count"] == 0
        assert result["error_count"] == 2

        from sqlalchemy.orm import sessionmaker

        from infrastructure.db.repositories import (
            SQLAlchemyCustomerRepository,
            SQLAlchemyErrorRepository,
        )

        Session = sessionmaker(bind=engine)
        fresh_session = Session()
        customer_repo = SQLAlchemyCustomerRepository(fresh_session, task_id=task.id)
        assert customer_repo.count_by_task(task.id) == 0

        error_repo = SQLAlchemyErrorRepository(fresh_session)
        assert len(error_repo.list_by_task(task.id)) == 2
        fresh_session.close()

    def test_empty_chunk_returns_zero_counts(self, celery_task_fixture):
        process_csv_chunk, session, engine, _csv_map = celery_task_fixture

        import infrastructure.celery.tasks as task_module

        storage = task_module.LocalFileStorage()
        csv_content = b"Email,Subscription Date,Website\n"
        file_path = storage.save("empty.csv", csv_content)

        from infrastructure.db.repositories import SQLAlchemyTaskRepository

        task_repo = SQLAlchemyTaskRepository(session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PENDING,
            total_rows=0,
            file_path=file_path,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        task_repo.save(task)
        session.commit()

        result = process_csv_chunk.run(str(task.id), 0)

        assert result["valid_count"] == 0
        assert result["error_count"] == 0

        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=engine)
        fresh_session = Session()
        task_repo2 = SQLAlchemyTaskRepository(fresh_session)
        found_task = task_repo2.get(task.id)
        assert found_task is not None
        assert found_task.status == TaskStatus.PENDING
        fresh_session.close()
