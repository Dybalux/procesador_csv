"""Tests de integración para repositorios SQLAlchemy.

Usan PostgreSQL via testcontainers para tests realistas.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from domain.entities import Customer, ProcessingTask, RowValidationError, TaskStatus
from domain.value_objects import Email, SubscriptionDate, Url
from infrastructure.db.repositories import (
    SQLAlchemyCustomerRepository,
    SQLAlchemyErrorRepository,
    SQLAlchemyTaskRepository,
)


class TestSQLAlchemyTaskRepository:
    def test_get_returns_none_for_missing_task(self, db_session: Session) -> None:
        repo = SQLAlchemyTaskRepository(db_session)
        assert repo.get(uuid4()) is None

    def test_save_and_get_roundtrip(self, db_session: Session) -> None:
        repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PENDING,
            total_rows=100,
            processed_rows=0,
            file_path="/tmp/test.csv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        repo.save(task)
        db_session.commit()

        found = repo.get(task.id)
        assert found is not None
        assert found.id == task.id
        assert found.status == TaskStatus.PENDING
        assert found.total_rows == 100
        assert found.file_path == "/tmp/test.csv"

    def test_save_updates_existing_task(self, db_session: Session) -> None:
        repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PENDING,
            file_path="/tmp/test.csv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        repo.save(task)
        db_session.commit()

        task.transition_to(TaskStatus.PROCESSING)
        repo.save(task)
        db_session.commit()

        found = repo.get(task.id)
        assert found is not None
        assert found.status == TaskStatus.PROCESSING

    def test_save_and_advance_progress(self, db_session: Session) -> None:
        repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PENDING,
            total_rows=100,
            processed_rows=0,
            file_path="/tmp/test.csv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        repo.save(task)
        db_session.commit()

        task.transition_to(TaskStatus.PROCESSING)
        task.advance_progress(10)
        repo.save(task)
        db_session.commit()

        found = repo.get(task.id)
        assert found is not None
        assert found.status == TaskStatus.PROCESSING
        assert found.processed_rows == 10

    def test_advance_progress_tracks_correctly(self, db_session: Session) -> None:
        repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PROCESSING,
            total_rows=100,
            processed_rows=0,
            file_path="/tmp/test.csv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        repo.save(task)
        db_session.commit()

        # Advance progress
        task.advance_progress(25)
        repo.save(task)
        db_session.commit()

        found = repo.get(task.id)
        assert found is not None
        assert found.processed_rows == 25


class TestSQLAlchemyCustomerRepository:
    def test_add_bulk_and_get(self, db_session: Session) -> None:
        # Crear tarea primero para FK
        task_repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PROCESSING,
            total_rows=10,
            file_path="/tmp/test.csv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        task_repo.save(task)
        db_session.commit()

        customer_repo = SQLAlchemyCustomerRepository(db_session, task_id=task.id)

        customers = [
            Customer(
                id=uuid4(),
                email=Email("alice@example.com"),
                website=Url("https://alice.com"),
                subscription_date=SubscriptionDate(date(2024, 1, 15)),
            ),
            Customer(
                id=uuid4(),
                email=Email("bob@example.com"),
                website=Url("https://bob.dev"),
                subscription_date=SubscriptionDate(date(2024, 2, 20)),
            ),
        ]
        customer_repo.add_bulk(customers)
        db_session.commit()

        found = customer_repo.get(customers[0].id)
        assert found is not None
        assert found.email.value == "alice@example.com"

    def test_count_by_task(self, db_session: Session) -> None:
        task_repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PROCESSING,
            total_rows=10,
            file_path="/tmp/test.csv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        task_repo.save(task)
        db_session.commit()

        customer_repo = SQLAlchemyCustomerRepository(db_session, task_id=task.id)

        customers = [
            Customer(
                id=uuid4(),
                email=Email(f"user{i}@example.com"),
                website=Url("https://example.com"),
                subscription_date=SubscriptionDate(date(2024, 1, 15)),
            )
            for i in range(5)
        ]
        customer_repo.add_bulk(customers)
        db_session.commit()

        assert customer_repo.count_by_task(task.id) == 5


class TestSQLAlchemyErrorRepository:
    def test_add_bulk_and_list_by_task(self, db_session: Session) -> None:
        # Crear tarea primero para FK
        task_repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PROCESSING,
            total_rows=10,
            file_path="/tmp/test.csv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        task_repo.save(task)
        db_session.commit()

        error_repo = SQLAlchemyErrorRepository(db_session)

        errors = [
            RowValidationError(
                id=uuid4(),
                task_id=task.id,
                row_number=1,
                raw_data={"email": "bad"},
                reason="Invalid email",
            ),
            RowValidationError(
                id=uuid4(),
                task_id=task.id,
                row_number=2,
                raw_data={"date": "not-a-date"},
                reason="Invalid date",
            ),
        ]
        error_repo.add_bulk(errors)
        db_session.commit()

        found = error_repo.list_by_task(task.id)
        assert len(found) == 2
        assert found[0].row_number == 1
        assert found[1].row_number == 2

    def test_list_by_task_returns_empty_for_no_errors(self, db_session: Session) -> None:
        error_repo = SQLAlchemyErrorRepository(db_session)
        found = error_repo.list_by_task(uuid4())
        assert found == []

    def test_count_by_task(self, db_session: Session) -> None:
        # Crear tarea primero para FK
        task_repo = SQLAlchemyTaskRepository(db_session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PROCESSING,
            total_rows=10,
            file_path="/tmp/test.csv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        task_repo.save(task)
        db_session.commit()

        error_repo = SQLAlchemyErrorRepository(db_session)

        errors = [
            RowValidationError(
                id=uuid4(),
                task_id=task.id,
                row_number=i,
                raw_data={},
                reason="Error",
            )
            for i in range(1, 4)  # row_number > 0
        ]
        error_repo.add_bulk(errors)
        db_session.commit()

        assert error_repo.count_by_task(task.id) == 3

    def test_count_by_task_returns_zero_for_no_errors(self, db_session: Session) -> None:
        error_repo = SQLAlchemyErrorRepository(db_session)
        assert error_repo.count_by_task(uuid4()) == 0
