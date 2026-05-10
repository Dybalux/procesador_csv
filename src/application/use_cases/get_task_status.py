"""Caso de uso: consultar estado de una tarea."""

from __future__ import annotations

from uuid import UUID

from application.interfaces import TaskStatusDTO
from domain.exceptions import TaskNotFound
from domain.ports import TaskRepository


class GetTaskStatus:
    """Busca una tarea por ID y retorna su estado como DTO."""

    def __init__(self, task_repo: TaskRepository) -> None:
        self._task_repo = task_repo

    def __call__(self, task_id: UUID) -> TaskStatusDTO:
        """Retorna el DTO de estado; lanza TaskNotFound si no existe."""
        task = self._task_repo.get(task_id)
        if task is None:
            raise TaskNotFound(str(task_id))
        return TaskStatusDTO(
            status=task.status.value,
            processed_rows=task.processed_rows,
            total_rows=task.total_rows,
            created_at=task.created_at,
        )
