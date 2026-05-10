"""DTOs de la capa de aplicación.

Estos modelos Pydantic definen los contratos de entrada/salida
entre los casos de uso y los adaptadores (web, workers, etc.).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Respuesta tras subir un archivo CSV."""

    task_id: UUID


class TaskStatusDTO(BaseModel):
    """Estado actual de una tarea de procesamiento."""

    status: str
    processed_rows: int
    total_rows: int | None
    created_at: datetime
