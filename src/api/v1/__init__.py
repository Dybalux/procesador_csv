"""API router para versión 1."""

from __future__ import annotations

from fastapi import APIRouter

from api.v1.endpoints import tasks, upload

api_router = APIRouter()
api_router.include_router(upload.router)
api_router.include_router(tasks.router)
