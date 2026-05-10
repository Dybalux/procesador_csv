"""Funciones de inyección de dependencias para FastAPI."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from domain.ports import FileStorage, TaskRepository, UnitOfWork, ValidationRule
from domain.validation_rules import DateRule, EmailRule, UrlRule
from infrastructure.db.connection import SessionLocal
from infrastructure.db.repositories import SQLAlchemyTaskRepository
from infrastructure.db.uow import SQLAlchemyUnitOfWork
from infrastructure.storage.local_file_storage import LocalFileStorage


def get_task_repo() -> Generator[TaskRepository, Any, None]:
    """Provee un repositorio de tareas con commit/rollback automático."""
    session = SessionLocal()
    repo = SQLAlchemyTaskRepository(session)
    try:
        yield repo
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_file_storage() -> FileStorage:
    """Provee almacenamiento local de archivos."""
    return LocalFileStorage()


def get_uow() -> UnitOfWork:
    """Provee una unidad de trabajo SQLAlchemy."""
    return SQLAlchemyUnitOfWork()


def get_validation_rules() -> list[ValidationRule]:
    """Provee las reglas de validación por defecto."""
    return [EmailRule(), UrlRule(), DateRule()]
