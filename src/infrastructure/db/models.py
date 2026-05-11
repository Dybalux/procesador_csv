"""Modelos ORM SQLAlchemy 2.0.

Mapean las entidades de dominio a tablas relacionales.  CustomerORM
incluye task_id como clave foránea aunque la entidad Customer no la
tenga — la relación es infraestructura-only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.connection import Base


class ProcessingTaskORM(Base):
    """ORM para tareas de procesamiento de CSV."""

    __tablename__ = "processing_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    file_path: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CustomerORM(Base):
    """ORM para clientes validados."""

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_tasks.id"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255))
    website: Mapped[str] = mapped_column(String(255))
    subscription_date: Mapped[datetime.date] = mapped_column(Date)


class RowValidationErrorORM(Base):
    """ORM para errores de validación por fila."""

    __tablename__ = "row_validation_errors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_tasks.id"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(500))
