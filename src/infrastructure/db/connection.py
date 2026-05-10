"""Configuración de base de datos SQLAlchemy 2.0.

Provee el engine, la session factory y la base declarativa para
los modelos ORM.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://user:pass@localhost/procesador_csv",
)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
