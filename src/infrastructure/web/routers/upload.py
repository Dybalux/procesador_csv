"""Router para subida de archivos CSV."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from application.interfaces import UploadResponse
from application.use_cases.upload_csv import UploadCSV
from domain.ports import FileStorage, TaskRepository
from infrastructure.web.dependencies import get_file_storage, get_task_repo

router = APIRouter()

MAX_FILE_SIZE = 104_857_600  # 100 MB


@router.post(
    "/api/v1/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UploadResponse,
)
def upload_csv(
    file: UploadFile,
    file_storage: FileStorage = Depends(get_file_storage),
    task_repo: TaskRepository = Depends(get_task_repo),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV",
        )

    content = file.file.read()

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File too large",
        )

    use_case = UploadCSV(file_storage, task_repo)
    task_id = use_case(content, file.filename)
    return UploadResponse(task_id=task_id)
