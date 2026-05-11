"""Caso de uso: procesar un chunk de filas CSV.

Aplica reglas de validación en orden, separa filas válidas de
inválidas, persiste ambas en bulk dentro de una unidad de trabajo,
y actualiza el contador de filas procesadas de la tarea.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from domain.entities import Customer, RowValidationError, TaskStatus
from domain.exceptions import TaskNotFound, ValidationFailed
from domain.ports import (
    CustomerRepository,
    ErrorRepository,
    TaskRepository,
    UnitOfWork,
    ValidationRule,
)
from domain.value_objects import Email, SubscriptionDate, Url


@dataclass(frozen=True, slots=True)
class ChunkResult:
    """Resultado del procesamiento de un chunk."""

    valid_count: int
    error_count: int


class ProcessChunk:
    """Procesa un lote de filas CSV aplicando reglas de validación."""

    def __init__(
        self,
        task_repo: TaskRepository,
        customer_repo: CustomerRepository,
        error_repo: ErrorRepository,
        uow: UnitOfWork,
        rules: list[ValidationRule],
    ) -> None:
        self._task_repo = task_repo
        self._customer_repo = customer_repo
        self._error_repo = error_repo
        self._uow = uow
        self._rules = rules

    def __call__(
        self,
        task_id: UUID,
        rows: list[dict[str, Any]],
        chunk_offset: int = 0,
    ) -> ChunkResult:
        """Procesa las filas, persiste resultados y retorna conteos."""
        task = self._task_repo.get(task_id)
        if task is None:
            raise TaskNotFound(str(task_id))

        if task.status == TaskStatus.PENDING:
            task.transition_to(TaskStatus.PROCESSING)
            self._task_repo.save(task)

        valid: list[Customer] = []
        errors: list[RowValidationError] = []

        for idx, row in enumerate(rows):
            row_number = chunk_offset + idx + 1
            reason = self._validate_row(row)
            if reason is None:
                customer = self._build_customer(row)
                if customer is not None:
                    valid.append(customer)
                else:
                    errors.append(
                        RowValidationError(
                            id=uuid4(),
                            task_id=task_id,
                            row_number=row_number,
                            raw_data=row,
                            reason="Failed to build customer from row",
                        )
                    )
            else:
                errors.append(
                    RowValidationError(
                        id=uuid4(),
                        task_id=task_id,
                        row_number=row_number,
                        raw_data=row,
                        reason=reason,
                    )
                )

        with self._uow:
            self._customer_repo.add_bulk(valid)
            self._error_repo.add_bulk(errors)
            task.advance_progress(len(rows))
            if task.total_rows is not None and task.processed_rows >= task.total_rows:
                task.transition_to(TaskStatus.COMPLETED)
            self._task_repo.save(task)
            self._uow.commit()

        return ChunkResult(valid_count=len(valid), error_count=len(errors))

    def _validate_row(self, row: dict[str, Any]) -> str | None:
        for rule in self._rules:
            reason = rule.validate(row)
            if reason is not None:
                return reason
        return None

    def _build_customer(self, row: dict[str, Any]) -> Customer | None:
        try:
            return Customer(
                id=uuid4(),
                email=Email(str(row["email"])),
                website=Url(str(row["website"])),
                subscription_date=SubscriptionDate(
                    date.fromisoformat(str(row["subscription_date"]))
                ),
            )
        except (KeyError, ValueError, ValidationFailed):
            return None
