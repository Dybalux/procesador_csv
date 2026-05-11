"""Configuración centralizada vía variables de entorno.

Toda la configuración del proyecto se inyecta por env vars,
respetando el principio de "12-factor app".  Cada parámetro tiene
un valor por defecto razonable para desarrollo local.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings del procesador CSV."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Base de datos
    # ------------------------------------------------------------------
    DATABASE_URL: str = (
        "postgresql+psycopg2://user:pass@localhost/procesador_csv"
    )
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # ------------------------------------------------------------------
    # Celery
    # ------------------------------------------------------------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_CONCURRENCY: int = 4
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1

    # ------------------------------------------------------------------
    # Procesamiento de CSV
    # ------------------------------------------------------------------
    CHUNK_SIZE: int = 1000
    MAX_FILE_SIZE: int = 104_857_600  # 100 MB

    # ------------------------------------------------------------------
    # API (Uvicorn)
    # ------------------------------------------------------------------
    UVICORN_HOST: str = "0.0.0.0"
    UVICORN_PORT: int = 8000
    UVICORN_WORKERS: int = 1
    UVICORN_RELOAD: bool = False

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    UPLOAD_BASE_DIR: str = "/tmp/procesador_csv/uploads"


# Singleton — importar desde cualquier módulo
settings = Settings()
