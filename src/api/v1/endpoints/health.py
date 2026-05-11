"""Endpoint de health check."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Respuesta del health check."""

    status: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Retorna el estado de la aplicación."""
    return HealthResponse(status="ok")
