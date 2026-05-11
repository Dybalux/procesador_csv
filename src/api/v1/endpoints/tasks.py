"""Endpoint para consulta de estado de tareas."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from application.interfaces import TaskStatusDTO
from application.use_cases.get_task_status import GetTaskStatus
from domain.exceptions import TaskNotFound
from domain.ports import TaskRepository
from infrastructure.web.dependencies import get_task_repo

router = APIRouter(tags=["tasks"])


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusDTO,
)
def get_task_status(
    task_id: UUID,
    task_repo: TaskRepository = Depends(get_task_repo),
) -> TaskStatusDTO:
    use_case = GetTaskStatus(task_repo)
    try:
        return use_case(task_id)
    except TaskNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
