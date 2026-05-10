"""Tests de integración para repositorios SQLAlchemy.

Usan SQLite en memoria para verificar el mapeo ORM sin necesidad
de PostgreSQL.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domain.entities import Customer, ProcessingTask, RowValidationError, TaskStatus
from domain.value_objects import Email, SubscriptionDate, Url
from infrastructure.db.connection import Base
from infrastructure.db.repositories import (
    SQLAlchemyCustomerRepository,
    SQLAlchemyErrorRepository,
    SQLAlchemyTaskRepository,
)

# Importar modelos para registrar metadata
import infrastructure.db.models  # noqa: F401


@pytest.fixture
def session():
    """Sesión SQLAlchemy sobre SQLite en memoria."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestSQLAlchemyTaskRepository:
    def test_get_returns_none_for_missing_task(self, session) -> None:
        repo = SQLAlchemyTaskRepository(session)
        assert repo.get(uuid4()) is None

    def test_save_and_get_roundtrip(self, session) -> None:
        repo = SQLAlchemyTaskRepository(session)
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
        session.commit()

        found = repo.get(task.id)
        assert found is not None
        assert found.id == task.id
        assert found.status == TaskStatus.PENDING
        assert found.total_rows == 100
        assert found.file_path == "/tmp/test.csv"

    def test_save_updates_existing_task(self, session) -> None:
        repo = SQLAlchemyTaskRepository(session)
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PENDING,
            file_path="/tmp/test.csv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        repo.save(task)
        session.commit()

        task.transition_to(TaskStatus.PROCESSING)
        repo.save(task)
        session.commit()

        found = repo.get(task.id)
        assert found is not None
        assert found.status == TaskStatus.PROCESSING


class TestSQLAlchemyCustomerRepository:
    def test_add_bulk_and_count_by_task(self, session) -> None:
        task_id = uuid4()
        repo = SQLAlchemyCustomerRepository(session, task_id=task_id)

        customers = [
            Customer(
                id=uuid4(),
                email=Email("alice@example.com"),
                website=Url("https://example.com"),
                subscription_date=SubscriptionDate(date(2024, 1, 15)),
            ),
            Customer(
                id=uuid4(),
                email=Email("bob@example.com"),
                website=Url("https://bob.dev"),
                subscription_date=SubscriptionDate(date(2024, 2, 20)),
            ),
        ]
        repo.add_bulk(customers)
        session.commit()

        assert repo.count_by_task(task_id) == 2

    def test_count_by_task_filters_by_task(self, session) -> None:
        task_a = uuid4()
        task_b = uuid4()
        repo_a = SQLAlchemyCustomerRepository(session, task_id=task_a)
        repo_b = SQLAlchemyCustomerRepository(session, task_id=task_b)

        repo_a.add_bulk([
            Customer(
                id=uuid4(),
                email=Email("a@example.com"),
                website=Url("https://a.com"),
                subscription_date=SubscriptionDate(date(2024, 1, 1)),
            ),
        ])
        repo_b.add_bulk([
            Customer(
                id=uuid4(),
                email=Email("b@example.com"),
                website=Url("https://b.com"),
                subscription_date=SubscriptionDate(date(2024, 1, 1)),
            ),
        ])
        session.commit()

        assert repo_a.count_by_task(task_a) == 1
        assert repo_a.count_by_task(task_b) == 1

    def test_merge_is_idempotent(self, session) -> None:
        task_id = uuid4()
        repo = SQLAlchemyCustomerRepository(session, task_id=task_id)
        customer_id = uuid4()
        customer = Customer(
            id=customer_id,
            email=Email("alice@example.com"),
            website=Url("https://example.com"),
            subscription_date=SubscriptionDate(date(2024, 1, 15)),
        )

        repo.add_bulk([customer])
        session.commit()

        repo.add_bulk([customer])
        session.commit()

        assert repo.count_by_task(task_id) == 1


class TestSQLAlchemyErrorRepository:
    def test_add_bulk_and_list_by_task(self, session) -> None:
        task_id = uuid4()
        repo = SQLAlchemyErrorRepository(session)

        errors = [
            RowValidationError(
                id=uuid4(),
                task_id=task_id,
                row_number=1,
                raw_data={"email": "bad"},
                reason="Invalid email",
            ),
            RowValidationError(
                id=uuid4(),
                task_id=task_id,
                row_number=2,
                raw_data={"website": "nope"},
                reason="Invalid URL",
            ),
        ]
        repo.add_bulk(errors)
        session.commit()

        found = repo.list_by_task(task_id)
        assert len(found) == 2
        reasons = {e.reason for e in found}
        assert reasons == {"Invalid email", "Invalid URL"}

    def test_list_by_task_filters_by_task(self, session) -> None:
        repo = SQLAlchemyErrorRepository(session)
        task_a = uuid4()
        task_b = uuid4()

        repo.add_bulk([
            RowValidationError(
                id=uuid4(),
                task_id=task_a,
                row_number=1,
                raw_data={},
                reason="err A",
            ),
        ])
        repo.add_bulk([
            RowValidationError(
                id=uuid4(),
                task_id=task_b,
                row_number=1,
                raw_data={},
                reason="err B",
            ),
        ])
        session.commit()

        assert len(repo.list_by_task(task_a)) == 1
        assert repo.list_by_task(task_a)[0].reason == "err A"
        assert len(repo.list_by_task(task_b)) == 1
        assert repo.list_by_task(task_b)[0].reason == "err B"
