"""Puertos de dominio (interfaces).

Los puertos son `typing.Protocol`: definen contratos sin imponer herencia.
Cualquier clase que implemente los métodos indicados es compatible.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol
from uuid import UUID

from domain.entities import Customer, ProcessingTask, RowValidationError


class CustomerRepository(Protocol):
    """Persistencia de clientes validados."""

    def add_bulk(self, customers: Iterable[Customer]) -> None:
        """Persiste un lote de clientes dentro de la unidad de trabajo actual."""
        ...

    def count_by_task(self, task_id: UUID) -> int:
        """Retorna cuántos clientes fueron persistidos para una tarea."""
        ...


class ErrorRepository(Protocol):
    """Persistencia de errores de validación."""

    def add_bulk(self, errors: Iterable[RowValidationError]) -> None:
        """Persiste un lote de errores dentro de la unidad de trabajo actual."""
        ...

    def list_by_task(self, task_id: UUID) -> list[RowValidationError]:
        """Lista todos los errores de validación para una tarea."""
        ...


class TaskRepository(Protocol):
    """Persistencia de tareas de procesamiento."""

    def get(self, task_id: UUID) -> ProcessingTask | None:
        """Busca una tarea por ID. Retorna None si no existe."""
        ...

    def save(self, task: ProcessingTask) -> None:
        """Persiste una tarea nueva o actualizada."""
        ...



class FileStorage(Protocol):
    """Almacenamiento de archivos CSV temporales."""

    def save(self, filename: str, content: bytes) -> str:
        """Guarda un archivo y retorna su path."""
        ...

    def read_chunks(self, path: str, chunk_size: int) -> Iterable[list[dict[str, str]]]:
        """Lee un archivo CSV por chunks de filas."""
        ...

    def delete(self, path: str) -> None:
        """Elimina un archivo del storage."""
        ...


class UnitOfWork(Protocol):
    """Unidad de trabajo para transacciones atómicas.

    Uso recomendado como context manager:

        with uow:
            repo.add_bulk(customers)
            uow.commit()
        # rollback automático si la salida es por excepción
    """

    def __enter__(self) -> UnitOfWork:
        """Inicia la unidad de trabajo."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Hace rollback automático si salió por excepción, sin suprimir el error."""
        ...

    def commit(self) -> None:
        """Confirma la transacción actual."""
        ...

    def rollback(self) -> None:
        """Revierte la transacción actual."""
        ...


class ValidationRule(Protocol):
    """Regla de validación aplicable a una fila CSV."""

    def validate(self, row: dict[str, Any]) -> str | None:
        """Valida una fila. Retorna None si es válida, o un mensaje de error."""
        ...
