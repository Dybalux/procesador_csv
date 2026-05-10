"""Fakes en memoria para tests unitarios de casos de uso.

Implementaciones simples de los puertos de dominio que permiten
probar la lógica de aplicación sin infraestructura real.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from domain.entities import Customer, ProcessingTask, RowValidationError
from domain.ports import (
    CustomerRepository,
    ErrorRepository,
    FileStorage,
    TaskRepository,
    UnitOfWork,
)


class FakeTaskRepository:
    """Repositorio de tareas en memoria."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, ProcessingTask] = {}

    def get(self, task_id: UUID) -> ProcessingTask | None:
        return self._tasks.get(task_id)

    def save(self, task: ProcessingTask) -> None:
        self._tasks[task.id] = task


class FakeCustomerRepository:
    """Repositorio de clientes en memoria.

    Nota: la entidad `Customer` no tiene `task_id`, por lo que
    `count_by_task` retorna el total acumulado sin filtrar.
    """

    def __init__(self) -> None:
        self._customers: list[Customer] = []

    def add_bulk(self, customers: Iterable[Customer]) -> None:
        self._customers.extend(customers)

    def count_by_task(self, task_id: UUID) -> int:
        return len(self._customers)


class FakeErrorRepository:
    """Repositorio de errores de validación en memoria."""

    def __init__(self) -> None:
        self._errors: list[RowValidationError] = []

    def add_bulk(self, errors: Iterable[RowValidationError]) -> None:
        self._errors.extend(errors)

    def list_by_task(self, task_id: UUID) -> list[RowValidationError]:
        return [e for e in self._errors if e.task_id == task_id]


class FakeFileStorage:
    """Almacenamiento de archivos en memoria (dict)."""

    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def save(self, filename: str, content: bytes) -> str:
        path = f"/tmp/{filename}"
        self._files[path] = content
        return path

    def read_chunks(self, path: str, chunk_size: int) -> Iterable[list[dict[str, str]]]:
        raise NotImplementedError

    def delete(self, path: str) -> None:
        self._files.pop(path, None)


class FakeUnitOfWork:
    """Unidad de trabajo en memoria (no-op)."""

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
