"""Excepciones de dominio.

Todas las excepciones de negocio heredan de `DomainException`.
Esto permite capturar cualquier error de dominio con un solo `except`.
"""


class DomainException(Exception):  # noqa: N818
    """Raíz de todas las excepciones de dominio."""

    pass


class TaskNotFound(DomainException):
    """Se solicita una tarea que no existe en el sistema."""

    def __init__(self, task_id: str) -> None:
        super().__init__(f"Task '{task_id}' not found.")
        self.task_id = task_id


class ValidationFailed(DomainException):
    """Una regla de validación de negocio falló."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
