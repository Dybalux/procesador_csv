"""Entidades de dominio.

Las entidades tienen identidad propia, mutan de estado, y encapsulan
invariantes de negocio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from domain.exceptions import ValidationFailed
from domain.value_objects import Email, SubscriptionDate, Url


class TaskStatus(str, Enum):
    """Estados posibles de una tarea de procesamiento."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Transiciones de estado válidas: PENDING → PROCESSING → (COMPLETED | FAILED)
_VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.PROCESSING},
    TaskStatus.PROCESSING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
}


@dataclass(slots=True, eq=False)
class Customer:
    """Entidad que representa un cliente validado."""

    id: UUID
    email: Email
    website: Url
    subscription_date: SubscriptionDate

    def __post_init__(self) -> None:
        if self.email is None or self.website is None or self.subscription_date is None:
            raise ValidationFailed("Customer fields cannot be None.")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Customer) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(slots=True, eq=False)
class RowValidationError:
    """Entidad que registra un fallo de validación en una fila CSV."""

    id: UUID
    task_id: UUID
    row_number: int
    raw_data: dict[str, Any]
    reason: str

    def __post_init__(self) -> None:
        if self.row_number <= 0:
            raise ValidationFailed(f"row_number must be > 0, got {self.row_number}")
        if not self.reason or not str(self.reason).strip():
            raise ValidationFailed("reason cannot be empty.")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RowValidationError) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(slots=True, eq=False)
class ProcessingTask:
    """Entidad que representa una tarea de procesamiento de CSV."""

    id: UUID
    status: TaskStatus = TaskStatus.PENDING
    total_rows: int | None = None
    processed_rows: int = 0
    file_path: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.total_rows is not None and self.processed_rows > self.total_rows:
            raise ValidationFailed(
                f"processed_rows ({self.processed_rows}) cannot exceed "
                f"total_rows ({self.total_rows})."
            )

    def transition_to(self, new_status: TaskStatus) -> None:
        """Cambia el estado validando la máquina de estados."""
        if new_status not in _VALID_TRANSITIONS.get(self.status, set()):
            raise ValidationFailed(
                f"Invalid state transition: {self.status.value} → {new_status.value}"
            )
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

    def advance_progress(self, count: int) -> None:
        """Incrementa filas procesadas manteniendo la invariante."""
        if count < 0:
            raise ValidationFailed(f"advance_progress count must be >= 0, got {count}")
        self.processed_rows += count
        if self.total_rows is not None and self.processed_rows > self.total_rows:
            raise ValidationFailed(
                f"processed_rows ({self.processed_rows}) cannot exceed "
                f"total_rows ({self.total_rows})."
            )
        self.updated_at = datetime.now(timezone.utc)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ProcessingTask) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
