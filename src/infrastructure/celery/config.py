"""Configuración de la aplicación Celery.

Define el broker Redis y la queue por defecto para tareas de
procesamiento CSV.
"""

from __future__ import annotations

import os

from celery import Celery

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "procesador_csv",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["infrastructure.celery.tasks"],
)

celery_app.conf.task_routes = {
    "infrastructure.celery.tasks.process_csv_chunk": {"queue": "csv_processing"},
}

celery_app.conf.task_default_queue = "csv_processing"
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
