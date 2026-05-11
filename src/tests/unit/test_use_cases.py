"""Tests unitarios de casos de uso con fakes en memoria.

Verifican que UploadCSV, GetTaskStatus y ProcessChunk comporten
correctamente sin necesidad de DB real ni Celery.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from application.interfaces import TaskStatusDTO
from application.use_cases.get_task_status import GetTaskStatus
from application.use_cases.process_chunk import ChunkResult, ProcessChunk
from application.use_cases.upload_csv import UploadCSV
from domain.entities import ProcessingTask, TaskStatus
from domain.exceptions import TaskNotFound
from domain.validation_rules import DateRule, EmailRule, UrlRule
from tests.unit.fakes import (
    FakeCustomerRepository,
    FakeErrorRepository,
    FakeFileStorage,
    FakeTaskRepository,
    FakeUnitOfWork,
)


class TestUploadCSV:
    def test_upload_creates_task_and_returns_task_id(self) -> None:
        storage = FakeFileStorage()
        task_repo = FakeTaskRepository()
        use_case = UploadCSV(storage, task_repo)

        task_id = use_case(b"some,csv\n1,2", "test.csv")

        assert task_id is not None
        task = task_repo.get(task_id)
        assert task is not None
        assert task.status == TaskStatus.PENDING
        assert task.file_path == "/tmp/test.csv"
        assert storage._files == {"/tmp/test.csv": b"some,csv\n1,2"}


class TestGetTaskStatus:
    def test_returns_dto_for_existing_task(self) -> None:
        task_repo = FakeTaskRepository()
        task = ProcessingTask(
            id=uuid4(),
            status=TaskStatus.PROCESSING,
            total_rows=100,
            processed_rows=50,
        )
        task_repo.save(task)
        use_case = GetTaskStatus(task_repo)

        dto = use_case(task.id)

        assert isinstance(dto, TaskStatusDTO)
        assert dto.status == "PROCESSING"
        assert dto.processed_rows == 50
        assert dto.total_rows == 100

    def test_raises_task_not_found_for_missing_task(self) -> None:
        task_repo = FakeTaskRepository()
        use_case = GetTaskStatus(task_repo)

        with pytest.raises(TaskNotFound):
            use_case(uuid4())


class TestProcessChunk:
    def _make_use_case(
        self,
        task_repo: FakeTaskRepository | None = None,
        customer_repo: FakeCustomerRepository | None = None,
        error_repo: FakeErrorRepository | None = None,
        uow: FakeUnitOfWork | None = None,
        rules: list | None = None,
    ) -> ProcessChunk:
        return ProcessChunk(
            task_repo=task_repo or FakeTaskRepository(),
            customer_repo=customer_repo or FakeCustomerRepository(),
            error_repo=error_repo or FakeErrorRepository(),
            uow=uow or FakeUnitOfWork(),
            rules=rules or [EmailRule(), UrlRule(), DateRule()],
        )

    def test_processes_all_valid_rows(self) -> None:
        task_repo = FakeTaskRepository()
        customer_repo = FakeCustomerRepository()
        error_repo = FakeErrorRepository()
        task = ProcessingTask(id=uuid4(), status=TaskStatus.PENDING, total_rows=2)
        task_repo.save(task)
        use_case = self._make_use_case(task_repo, customer_repo, error_repo)

        rows = [
            {
                "email": "alice@example.com",
                "website": "https://example.com",
                "subscription_date": "2023-01-15",
            },
            {
                "email": "bob@example.com",
                "website": "http://example.org",
                "subscription_date": "2022-06-01",
            },
        ]

        result = use_case(task.id, rows)

        assert result == ChunkResult(valid_count=2, error_count=0)
        assert len(customer_repo._customers) == 2
        assert len(error_repo._errors) == 0
        assert task_repo.get(task.id).processed_rows == 2
        assert task_repo.get(task.id).status == TaskStatus.COMPLETED

    def test_separates_valid_and_invalid_rows(self) -> None:
        task_repo = FakeTaskRepository()
        customer_repo = FakeCustomerRepository()
        error_repo = FakeErrorRepository()
        task = ProcessingTask(id=uuid4(), status=TaskStatus.PENDING)
        task_repo.save(task)
        use_case = self._make_use_case(task_repo, customer_repo, error_repo)

        rows = [
            {
                "email": "alice@example.com",
                "website": "https://example.com",
                "subscription_date": "2023-01-15",
            },
            {
                "email": "bad-email",
                "website": "https://example.com",
                "subscription_date": "2023-01-15",
            },
            {
                "email": "bob@example.com",
                "website": "not-a-url",
                "subscription_date": "2023-01-15",
            },
            {
                "email": "charlie@example.com",
                "website": "https://example.com",
                "subscription_date": (date.today() + timedelta(days=1)).isoformat(),
            },
        ]

        result = use_case(task.id, rows, chunk_offset=0)

        assert result == ChunkResult(valid_count=1, error_count=3)
        assert len(customer_repo._customers) == 1
        assert len(error_repo._errors) == 3
        assert task_repo.get(task.id).processed_rows == 4

        # Verificar números de fila en errores
        error_rows = {e.row_number for e in error_repo._errors}
        assert error_rows == {2, 3, 4}

    def test_raises_task_not_found(self) -> None:
        use_case = self._make_use_case()

        with pytest.raises(TaskNotFound):
            use_case(uuid4(), [])

    def test_empty_chunk_advances_zero(self) -> None:
        task_repo = FakeTaskRepository()
        task = ProcessingTask(id=uuid4(), status=TaskStatus.PENDING)
        task_repo.save(task)
        use_case = self._make_use_case(task_repo)

        result = use_case(task.id, [])

        assert result == ChunkResult(valid_count=0, error_count=0)
        assert task_repo.get(task.id).processed_rows == 0

    def test_missing_field_creates_error(self) -> None:
        task_repo = FakeTaskRepository()
        error_repo = FakeErrorRepository()
        task = ProcessingTask(id=uuid4(), status=TaskStatus.PENDING)
        task_repo.save(task)
        use_case = self._make_use_case(task_repo, error_repo=error_repo)

        rows = [{"email": "alice@example.com"}]  # missing website and subscription_date

        result = use_case(task.id, rows)

        assert result.valid_count == 0
        assert result.error_count == 1
        assert len(error_repo._errors) == 1
        assert "Missing website field" in error_repo._errors[0].reason
