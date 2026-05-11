"""Configuración de base de datos SQLAlchemy 2.0.

Provee el engine, la session factory y la base declarativa para
los modelos ORM.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from infrastructure.config.settings import settings


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
