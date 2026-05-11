#!/bin/sh
# Script de inicio de la app con workers configurables

set -e

WORKERS="${UVICORN_WORKERS:-1}"
HOST="${UVICORN_HOST:-0.0.0.0}"
PORT="${UVICORN_PORT:-8000}"

echo "Starting Uvicorn with $WORKERS worker(s) on $HOST:$PORT"

exec uvicorn infrastructure.web.main:create_app \
    --factory \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS"
