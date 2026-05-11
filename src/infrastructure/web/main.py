"""FastAPI app factory con lifespan para inicializar DB."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import api_router
from api.v1.endpoints import health
from infrastructure.db.connection import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa tablas de DB al arrancar la aplicación."""
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    """Factory que retorna la aplicación FastAPI configurada."""
    app = FastAPI(
        title="Procesador CSV",
        description="Procesador de CSV asíncrono con arquitectura hexagonal",
        version="0.1.0",
        lifespan=lifespan,
    )
    # Health check en raíz (sin /api prefix)
    app.include_router(health.router)
    # API v1 con prefijo /api
    app.include_router(api_router, prefix="/api")
    return app
