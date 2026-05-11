"""Tareas Celery para procesamiento de CSV en background.

La tarea ``process_csv_chunk`` orquesta la lectura de un chunk,
la invocación del caso de uso ``ProcessChunk`` y la persistencia
mediante Unit of Work.
"""

from __future__ import annotations

from uuid import UUID

from application.use_cases.process_chunk import ProcessChunk
from domain.validation_rules import DateRule, EmailRule, UrlRule
from infrastructure.celery.config import celery_app
from infrastructure.config.settings import settings
from infrastructure.db.repositories import (
    SQLAlchemyCustomerRepository,
    SQLAlchemyErrorRepository,
    SQLAlchemyTaskRepository,
)
from infrastructure.db.uow import SQLAlchemyUnitOfWork
from infrastructure.storage.csv_mappers import CUSTOMERS_100_MAP
from infrastructure.storage.local_file_storage import LocalFileStorage


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def process_csv_chunk(self, task_id: str, chunk_offset: int) -> dict[str, int]:
    """Procesa un chunk de filas CSV de forma asíncrona.

    Args:
        task_id: UUID de la tarea como string.
        chunk_offset: Número de fila inicial (0-based) del chunk.

    Returns:
        Diccionario con ``valid_count`` y ``error_count``.
    """
    uow = SQLAlchemyUnitOfWork()
    task_repo = SQLAlchemyTaskRepository(uow.session)
    task = task_repo.get(UUID(task_id))
    if task is None:
        raise ValueError(f"Task {task_id} not found")

    storage = LocalFileStorage()
    rows = storage.read_chunk(
        task.file_path, settings.CHUNK_SIZE, chunk_offset, header_mapping=CUSTOMERS_100_MAP
    )

    if not rows:
        return {"valid_count": 0, "error_count": 0}

    customer_repo = SQLAlchemyCustomerRepository(uow.session, task_id=task.id)
    error_repo = SQLAlchemyErrorRepository(uow.session)
    rules = [EmailRule(), UrlRule(), DateRule()]

    process_chunk = ProcessChunk(task_repo, customer_repo, error_repo, uow, rules)
    result = process_chunk(task.id, rows, chunk_offset)

    return {"valid_count": result.valid_count, "error_count": result.error_count}
