"""Tests unitarios de entidades de dominio.

No dependen de ninguna infraestructura externa.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from domain.entities import Customer, ProcessingTask, RowValidationError, TaskStatus
from domain.exceptions import ValidationFailed
from domain.value_objects import Email, SubscriptionDate, Url


class TestCustomer:
    def test_create_valid_customer(self) -> None:
        customer = Customer(
            id=uuid4(),
            email=Email("alice@example.com"),
            website=Url("https://example.com"),
            subscription_date=SubscriptionDate(date.today() - timedelta(days=5)),
        )
        assert customer.email.value == "alice@example.com"

    def test_none_email_raises(self) -> None:
        with pytest.raises(ValidationFailed):
            Customer(
                id=uuid4(),
                email=None,
                website=Url("https://example.com"),
                subscription_date=SubscriptionDate(date.today() - timedelta(days=5)),
            )

    def test_none_website_raises(self) -> None:
        with pytest.raises(ValidationFailed):
            Customer(
                id=uuid4(),
                email=Email("alice@example.com"),
                website=None,
                subscription_date=SubscriptionDate(date.today() - timedelta(days=5)),
            )

    def test_none_subscription_date_raises(self) -> None:
        with pytest.raises(ValidationFailed):
            Customer(
                id=uuid4(),
                email=Email("alice@example.com"),
                website=Url("https://example.com"),
                subscription_date=None,
            )


class TestRowValidationError:
    def test_create_valid_error(self) -> None:
        err = RowValidationError(
            id=uuid4(),
            task_id=uuid4(),
            row_number=1,
            raw_data={"email": "bad"},
            reason="Invalid email",
        )
        assert err.row_number == 1
        assert err.reason == "Invalid email"

    @pytest.mark.parametrize("row_number", [0, -1, -100])
    def test_row_number_must_be_positive(self, row_number: int) -> None:
        with pytest.raises(ValidationFailed):
            RowValidationError(
                id=uuid4(),
                task_id=uuid4(),
                row_number=row_number,
                raw_data={},
                reason="Some error",
            )

    @pytest.mark.parametrize("reason", ["", "   ", None])
    def test_reason_cannot_be_empty(self, reason: str | None) -> None:
        with pytest.raises(ValidationFailed):
            RowValidationError(
                id=uuid4(),
                task_id=uuid4(),
                row_number=1,
                raw_data={},
                reason=reason,
            )


class TestProcessingTask:
    def test_default_status_is_pending(self) -> None:
        task = ProcessingTask(id=uuid4())
        assert task.status == TaskStatus.PENDING
        assert task.processed_rows == 0
        assert task.total_rows is None

    def test_valid_state_transitions(self) -> None:
        task = ProcessingTask(id=uuid4())
        task.transition_to(TaskStatus.PROCESSING)
        assert task.status == TaskStatus.PROCESSING

        task.transition_to(TaskStatus.COMPLETED)
        assert task.status == TaskStatus.COMPLETED

    def test_valid_transition_to_failed(self) -> None:
        task = ProcessingTask(id=uuid4())
        task.transition_to(TaskStatus.PROCESSING)
        task.transition_to(TaskStatus.FAILED)
        assert task.status == TaskStatus.FAILED

    def test_invalid_transition_pending_to_completed(self) -> None:
        task = ProcessingTask(id=uuid4())
        with pytest.raises(ValidationFailed):
            task.transition_to(TaskStatus.COMPLETED)

    def test_invalid_transition_completed_to_any(self) -> None:
        task = ProcessingTask(id=uuid4())
        task.transition_to(TaskStatus.PROCESSING)
        task.transition_to(TaskStatus.COMPLETED)
        with pytest.raises(ValidationFailed):
            task.transition_to(TaskStatus.FAILED)

    def test_processed_rows_cannot_exceed_total_rows_on_creation(self) -> None:
        with pytest.raises(ValidationFailed):
            ProcessingTask(id=uuid4(), total_rows=5, processed_rows=10)

    def test_advance_progress_valid(self) -> None:
        task = ProcessingTask(id=uuid4(), total_rows=10)
        task.advance_progress(3)
        assert task.processed_rows == 3
        task.advance_progress(4)
        assert task.processed_rows == 7

    def test_advance_progress_exceeds_total_rows(self) -> None:
        task = ProcessingTask(id=uuid4(), total_rows=5)
        with pytest.raises(ValidationFailed):
            task.advance_progress(10)

    def test_advance_progress_negative_count(self) -> None:
        task = ProcessingTask(id=uuid4(), total_rows=5)
        with pytest.raises(ValidationFailed):
            task.advance_progress(-1)

    def test_processed_rows_unbounded_when_total_is_none(self) -> None:
        task = ProcessingTask(id=uuid4(), total_rows=None)
        task.advance_progress(999_999)
        assert task.processed_rows == 999_999
