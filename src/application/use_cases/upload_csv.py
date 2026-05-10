"""Caso de uso: subir un archivo CSV.

Orchestra el almacenamiento del archivo y la creación de la tarea
de procesamiento en estado PENDING.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from domain.entities import ProcessingTask
from domain.ports import FileStorage, TaskRepository


class UploadCSV:
    """Recibe contenido de archivo CSV, lo persiste y crea una tarea."""

    def __init__(self, file_storage: FileStorage, task_repo: TaskRepository) -> None:
        self._file_storage = file_storage
        self._task_repo = task_repo

    def __call__(self, file_content: bytes, filename: str) -> UUID:
        """Guarda el archivo, crea tarea PENDING y retorna su ID."""
        file_path = self._file_storage.save(filename, file_content)
        task = ProcessingTask(id=uuid4(), file_path=file_path)
        self._task_repo.save(task)
        return task.id
