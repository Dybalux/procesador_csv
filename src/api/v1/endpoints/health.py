"""Endpoint de health check."""

from __future__ import annotations

import redis as redis_lib
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from infrastructure.config.settings import settings
from infrastructure.db.connection import engine

router = APIRouter(tags=["health"])


class ServiceStatus(BaseModel):
    """Estado de un servicio de infraestructura."""

    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    """Respuesta del health check con estado por servicio."""

    status: str
    services: dict[str, ServiceStatus]


def _check_database() -> ServiceStatus:
    """Verifica conectividad con PostgreSQL ejecutando SELECT 1."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return ServiceStatus(status="ok")
    except Exception as exc:  # noqa: BLE001
        return ServiceStatus(status="error", detail=str(exc))


def _check_redis() -> ServiceStatus:
    """Verifica conectividad con Redis mediante PING."""
    try:
        r = redis_lib.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2)
        r.ping()
        return ServiceStatus(status="ok")
    except Exception as exc:  # noqa: BLE001
        return ServiceStatus(status="error", detail=str(exc))


@router.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    """Retorna el estado de la aplicación y sus dependencias.

    Devuelve HTTP 200 si todos los servicios responden correctamente,
    HTTP 503 si alguno falla.
    """
    services = {
        "database": _check_database(),
        "redis": _check_redis(),
    }

    all_ok = all(s.status == "ok" for s in services.values())
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if all_ok else "degraded",
        services=services,
    )
