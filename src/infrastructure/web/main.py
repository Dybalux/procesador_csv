"""FastAPI app factory con lifespan para inicializar DB."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from infrastructure.db.connection import Base, engine
from infrastructure.web.routers import tasks, upload


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
    app.include_router(upload.router)
    app.include_router(tasks.router)
    return app
