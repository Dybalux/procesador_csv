"""Implementaciones SQLAlchemy de los puertos de repositorio.

Cada repositorio convierte entre entidades de dominio y modelos ORM.
CustomerORM recibe task_id vía el constructor del repositorio, ya que
la entidad Customer no expone ese campo.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.entities import Customer, ProcessingTask, RowValidationError, TaskStatus
from domain.value_objects import Email, SubscriptionDate, Url
from infrastructure.db.models import CustomerORM, ProcessingTaskORM, RowValidationErrorORM


class SQLAlchemyTaskRepository:
    """Persistencia de tareas con SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, task_id: UUID) -> ProcessingTask | None:
        """Busca una tarea por ID."""
        orm = self._session.get(ProcessingTaskORM, task_id)
        if orm is None:
            return None
        return ProcessingTask(
            id=orm.id,
            status=TaskStatus(orm.status),
            total_rows=orm.total_rows,
            processed_rows=orm.processed_rows,
            file_path=orm.file_path,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def save(self, task: ProcessingTask) -> None:
        """Persiste o actualiza una tarea."""
        orm = ProcessingTaskORM(
            id=task.id,
            status=task.status.value,
            total_rows=task.total_rows,
            processed_rows=task.processed_rows,
            file_path=task.file_path,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        self._session.merge(orm)


class SQLAlchemyCustomerRepository:
    """Persistencia de clientes con SQLAlchemy.

    El ``task_id`` se provee en el constructor porque la entidad
    :class:`domain.entities.Customer` no lo expone.
    """

    def __init__(self, session: Session, task_id: UUID | None = None) -> None:
        self._session = session
        self._task_id = task_id

    def add_bulk(self, customers: Iterable[Customer]) -> None:
        """Persiste un lote de clientes (merge para idempotencia)."""
        for customer in customers:
            orm = CustomerORM(
                id=customer.id,
                task_id=self._task_id,
                email=customer.email.value,
                website=customer.website.value,
                subscription_date=customer.subscription_date.value,
            )
            self._session.merge(orm)

    def get(self, customer_id: UUID) -> Customer | None:
        """Busca un cliente por ID."""
        orm = self._session.get(CustomerORM, customer_id)
        if orm is None:
            return None
        return Customer(
            id=orm.id,
            email=Email(orm.email),
            website=Url(orm.website),
            subscription_date=SubscriptionDate(orm.subscription_date),
        )

    def count_by_task(self, task_id: UUID) -> int:
        """Cuenta clientes asociados a una tarea."""
        stmt = (
            select(func.count())
            .select_from(CustomerORM)
            .where(CustomerORM.task_id == task_id)
        )
        return self._session.scalar(stmt) or 0


class SQLAlchemyErrorRepository:
    """Persistencia de errores de validación con SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_bulk(self, errors: Iterable[RowValidationError]) -> None:
        """Persiste un lote de errores (merge para idempotencia)."""
        for error in errors:
            orm = RowValidationErrorORM(
                id=error.id,
                task_id=error.task_id,
                row_number=error.row_number,
                raw_data=error.raw_data,
                reason=error.reason,
            )
            self._session.merge(orm)

    def list_by_task(self, task_id: UUID) -> list[RowValidationError]:
        """Lista errores de una tarea."""
        stmt = select(RowValidationErrorORM).where(
            RowValidationErrorORM.task_id == task_id
        )
        orms = self._session.scalars(stmt).all()
        return [
            RowValidationError(
                id=orm.id,
                task_id=orm.task_id,
                row_number=orm.row_number,
                raw_data=orm.raw_data,
                reason=orm.reason,
            )
            for orm in orms
        ]

    def count_by_task(self, task_id: UUID) -> int:
        """Cuenta errores asociados a una tarea."""
        stmt = (
            select(func.count())
            .select_from(RowValidationErrorORM)
            .where(RowValidationErrorORM.task_id == task_id)
        )
        return self._session.scalar(stmt) or 0
