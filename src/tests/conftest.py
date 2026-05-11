"""Fixtures compartidos para tests con PostgreSQL via testcontainers."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, Any, None]:
    """Levanta un contenedor PostgreSQL para toda la sesión de tests."""
    postgres = PostgresContainer("postgres:16-alpine")
    postgres.start()
    
    # Configurar URL de conexión
    os.environ["DATABASE_URL"] = postgres.get_connection_url()
    os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
    
    yield postgres
    
    postgres.stop()


@pytest.fixture(scope="session")
def db_engine(postgres_container: PostgresContainer) -> Generator[Any, Any, None]:
    """Crea el engine de SQLAlchemy conectado al contenedor PostgreSQL."""
    # Importar después de que el contenedor esté listo
    from infrastructure.db import models  # noqa: F401
    from infrastructure.db.connection import Base
    
    connection_url = postgres_container.get_connection_url()
    engine = create_engine(connection_url)
    
    # Crear todas las tablas
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Any) -> Generator[Session, Any, None]:
    """Proporciona una sesión de base de datos para tests."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    session = TestingSessionLocal()
    
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture(autouse=True)
def cleanup_db(db_engine: Any) -> Generator[None, Any, None]:
    """Limpia todas las tablas después de cada test."""
    yield
    # Después del test, truncar todas las tablas
    from infrastructure.db.connection import Base
    with db_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


@pytest.fixture
def file_storage(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """Proporciona un LocalFileStorage en directorio temporal."""
    from infrastructure.storage.local_file_storage import LocalFileStorage
    
    tmp_path = tmp_path_factory.mktemp("uploads")
    return LocalFileStorage(base_dir=str(tmp_path))
