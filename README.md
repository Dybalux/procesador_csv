# Procesador CSV Asíncrono

Procesador de archivos CSV con arquitectura limpia/hexagonal. Soporta archivos grandes, procesamiento por chunks en background con Celery, y persistencia en PostgreSQL.

## 🏗️ Arquitectura

**Arquitectura Hexagonal (Ports & Adapters)** con las siguientes capas:

```
src/
├── domain/              # Capa de dominio (puramente Python)
│   ├── entities.py      # Entidades de negocio
│   ├── value_objects.py # Email, Url, SubscriptionDate
│   ├── exceptions.py    # Excepciones de dominio
│   ├── ports.py         # Protocols (interfaces)
│   └── validation_rules.py # Reglas de validación
│
├── application/         # Casos de uso
│   ├── use_cases/       # UploadCSV, GetTaskStatus, ProcessChunk
│   └── interfaces.py    # DTOs (Pydantic)
│
└── infrastructure/      # Adaptadores
    ├── db/              # SQLAlchemy + PostgreSQL
    ├── storage/         # FileSystem local
    ├── celery/          # Workers + Redis
    └── web/             # FastAPI + routers
```

**Principio clave:** El dominio NO importa frameworks (FastAPI, Celery, SQLAlchemy, Pydantic).

## 🚀 Stack Tecnológico

- **Python 3.11** + Alpine Linux
- **FastAPI** - API REST
- **Celery 5.6** + **Redis** - Cola de tareas
- **PostgreSQL 15** - Base de datos
- **SQLAlchemy 2.0** - ORM con `Mapped[]`/`mapped_column()`
- **Pydantic v2** - Validación y DTOs
- **Alembic** - Migraciones de DB
- **Docker + Docker Compose** - Infraestructura

## 📋 Requisitos Previos

- Docker Engine 24+
- Docker Compose v2+
- curl (para probar la API)

## 🔧 Instalación y Setup

### 1. Clonar y entrar al proyecto

```bash
git clone <repo-url>
cd procesador_csv
```

### 2. Iniciar servicios

```bash
# Bajar todo si había algo corriendo
docker compose down -v

# Reconstruir imágenes (primera vez o después de cambios)
docker compose build --no-cache

# Levantar servicios
docker compose up -d
```

### 3. Verificar estado

```bash
docker compose ps
```

Esperar a ver:
- `db` → `(healthy)`
- `app` → `Up`
- `worker` → `Up`
- `redis` → `Up`

### 4. Aplicar migraciones (primera vez)

```bash
# Si las tablas no existen, aplicar migración de Alembic
docker compose exec app alembic upgrade head
```

## 🎯 Uso

### Subir un archivo CSV

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@customers-100.csv"
```

**Respuesta:**
```json
{"task_id": "xxxxx-xxxxx-xxxxx-xxxxx"}
```

El procesamiento es **automático**: la API encola los chunks en Celery sin intervención manual.

### Consultar estado de tarea

```bash
curl http://localhost:8000/api/v1/tasks/TU_TASK_ID
```

**Respuesta:**
```json
{
  "status": "PROCESSING",
  "processed_rows": 100,
  "total_rows": null,
  "created_at": "2026-05-11T01:45:13"
}
```

### Ver logs del worker en tiempo real

```bash
docker compose logs -f worker
```

### Verificar datos en PostgreSQL

```bash
docker compose exec db psql -U user -d procesador_csv -c "SELECT COUNT(*) FROM customers;"
```

## 🧪 Testing

```bash
# Tests unitarios
docker compose exec app pytest src/tests/unit/ -v

# Tests de integración
docker compose exec app pytest src/tests/integration/ -v

# Tests E2E
docker compose exec app pytest src/tests/e2e/ -v

# Todos los tests
docker compose exec app pytest
```

## 🗂️ Estructura del Proyecto

```
procesador_csv/
├── docker-compose.yml          # Servicios: app, worker, db, redis
├── Dockerfile                  # Multi-stage build con Alpine
├── docker-entrypoint.sh        # Entrypoint para permisos non-root
├── alembic.ini                 # Configuración Alembic
├── requirements.txt            # Dependencias Python
├── pyproject.toml             # Configuración proyecto
├── migrations/                 # Migraciones Alembic
│   ├── env.py
│   └── versions/
│       └── c6b4a68c61ab_initial_migration.py
└── src/
    ├── domain/                 # Lógica pura, sin frameworks
    ├── application/            # Casos de uso
    ├── infrastructure/         # Adaptadores (DB, Celery, Web)
    └── tests/                  # Tests unitarios, integración, E2E
```

## 🔒 Seguridad

- Contenedores corren como **usuario non-root** (`appuser`, UID 1000)
- Sin warnings de Celery por superuser privileges
- Entrypoint fixea permisos de volúmenes compartidos antes de bajar privilegios

## 🐛 Decisiones de Diseño Importantes

1. **Race condition DB → App**: Healthcheck en PostgreSQL con `pg_isready`. La app y worker esperan a que la DB esté `(healthy)` antes de iniciar.

2. **Volumen compartido**: `uploads_data` montado en `/tmp/procesador_csv/uploads` tanto para `app` como `worker`. Sin esto, el worker no encuentra los archivos subidos por la app.

3. **Retry automático Celery**: Si el worker intenta procesar antes de que la transacción del upload se haya commiteado, Celery hace retry automático (max 3 intentos, backoff exponencial).

4. **Idempotencia**: Cada fila del CSV genera un UUID único. Reprocesar un chunk no duplica customers.

## 📦 Migraciones de Base de Datos

```bash
# Crear nueva migración automáticamente
docker compose exec app alembic revision --autogenerate -m "descripción"

# Aplicar migraciones
docker compose exec app alembic upgrade head

# Ver versión actual
docker compose exec app alembic current
```

## 🛑 Detener servicios

```bash
# Bajar conservando datos
docker compose down

# Bajar eliminando TODO (incluyendo volúmenes de DB)
docker compose down -v
```

## 📝 Licencia

MIT
