"""Tests de integración para la tarea Celery process_csv_chunk.

Usan PostgreSQL via testcontainers para tests realistas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from application.use_cases.process_chunk import ProcessChunk
from domain.entities import ProcessingTask, TaskStatus
from domain.validation_rules import DateRule, EmailRule, UrlRule
from infrastructure.db.repositories import (
    SQLAlchemyCustomerRepository,
    SQLAlchemyErrorRepository,
    SQLAlchemyTaskRepository,
)
from infrastructure.db.uow import SQLAlchemyUnitOfWork
from infrastructure.storage.csv_mappers import CUSTOMERS_100_MAP
from infrastructure.storage.local_file_storage import LocalFileStorage


class TestProcessCSVChunk:
    def test_processes_valid_rows(
        self, db_engine: Any, file_storage: LocalFileStorage, db_session: Session
    ) -> None:
        csv_content = (
            b"Email,Subscription Date,Website\n"
            b"alice@example.com,2024-01-15,https://example.com\n"
            b"bob@example.com,2024-02-20,https://bob.dev\n"
        )
        file_path = file_storage.save("valid.csv", csv_content)

        task_repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PENDING,
            total_rows=2,
            file_path=file_path,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        task_repo.save(task)
        db_session.commit()

        # Leer chunk y procesar directamente con ProcessChunk
        rows = file_storage.read_chunk(
            file_path, chunk_size=1000, offset=0, header_mapping=CUSTOMERS_100_MAP
        )
        uow = SQLAlchemyUnitOfWork(session_factory=sessionmaker(bind=db_engine))
        customer_repo = SQLAlchemyCustomerRepository(uow.session, task_id=task.id)
        error_repo = SQLAlchemyErrorRepository(uow.session)
        task_repo_uow = SQLAlchemyTaskRepository(uow.session)
        rules = [EmailRule(), UrlRule(), DateRule()]
        process = ProcessChunk(task_repo_uow, customer_repo, error_repo, uow, rules)
        result = process(task.id, rows, 0)

        assert result.valid_count == 2
        assert result.error_count == 0
        assert customer_repo.count_by_task(task.id) == 2
        assert len(error_repo.list_by_task(task.id)) == 0

        final_task = task_repo_uow.get(task.id)
        assert final_task is not None
        assert final_task.status == TaskStatus.COMPLETED

    def test_processes_invalid_rows(
        self, db_engine: Any, file_storage: LocalFileStorage, db_session: Session
    ) -> None:
        csv_content = (
            b"Email,Subscription Date,Website\n"
            b"invalid-email,2024-01-15,https://example.com\n"
            b"bob@example.com,not-a-date,https://bob.dev\n"
        )
        file_path = file_storage.save("invalid.csv", csv_content)

        task_repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PENDING,
            total_rows=2,
            file_path=file_path,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        task_repo.save(task)
        db_session.commit()

        rows = file_storage.read_chunk(
            file_path, chunk_size=1000, offset=0, header_mapping=CUSTOMERS_100_MAP
        )
        uow = SQLAlchemyUnitOfWork(session_factory=sessionmaker(bind=db_engine))
        customer_repo = SQLAlchemyCustomerRepository(uow.session, task_id=task.id)
        error_repo = SQLAlchemyErrorRepository(uow.session)
        task_repo_uow = SQLAlchemyTaskRepository(uow.session)
        rules = [EmailRule(), UrlRule(), DateRule()]
        process = ProcessChunk(task_repo_uow, customer_repo, error_repo, uow, rules)
        result = process(task.id, rows, 0)

        assert result.valid_count == 0
        assert result.error_count == 2
        assert customer_repo.count_by_task(task.id) == 0
        assert len(error_repo.list_by_task(task.id)) == 2

    def test_empty_chunk_returns_zero_counts(
        self, db_engine: Any, file_storage: LocalFileStorage, db_session: Session
    ) -> None:
        csv_content = b"Email,Subscription Date,Website\n"
        file_path = file_storage.save("empty.csv", csv_content)

        task_repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PENDING,
            total_rows=0,
            file_path=file_path,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        task_repo.save(task)
        db_session.commit()

        rows = file_storage.read_chunk(
            file_path, chunk_size=1000, offset=0, header_mapping=CUSTOMERS_100_MAP
        )
        uow = SQLAlchemyUnitOfWork(session_factory=sessionmaker(bind=db_engine))
        customer_repo = SQLAlchemyCustomerRepository(uow.session, task_id=task.id)
        error_repo = SQLAlchemyErrorRepository(uow.session)
        task_repo_uow = SQLAlchemyTaskRepository(uow.session)
        rules = [EmailRule(), UrlRule(), DateRule()]
        process = ProcessChunk(task_repo_uow, customer_repo, error_repo, uow, rules)
        result = process(task.id, rows, 0)

        assert result.valid_count == 0
        assert result.error_count == 0

        final_task = task_repo_uow.get(task.id)
        assert final_task is not None
        assert final_task.status == TaskStatus.PENDING
