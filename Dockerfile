# syntax=docker/dockerfile:1
FROM python:3.11-alpine AS builder

WORKDIR /app
# Dependencias de build para compilar psycopg2 desde source en Alpine
RUN apk add --no-cache postgresql-dev gcc musl-dev linux-headers
RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-alpine

WORKDIR /app
# Runtime lib para psycopg2 + su-exec para cambiar de usuario en entrypoint
RUN apk add --no-cache libpq su-exec

# Crear usuario no-root para seguridad
RUN adduser -D -u 1000 appuser

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/
COPY pyproject.toml .
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PYTHONPATH=/app/src

EXPOSE 8000

COPY start-app.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start-app.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["start-app.sh"]
