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

## ⚙️ Configuración

Toda la configuración se realiza mediante **variables de entorno** (principio 12-factor app). Puedes modificar los valores editando el archivo `docker-compose.yml` o creando un archivo `.env` en la raíz del proyecto.

### Variables disponibles

#### Base de datos (`src/infrastructure/db/connection.py`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg2://user:pass@db/procesador_csv` | URL de conexión a PostgreSQL |
| `DB_POOL_SIZE` | `5` | Conexiones mantenidas permanentemente en el pool |
| `DB_MAX_OVERFLOW` | `10` | Conexiones extras que se pueden crear bajo demanda |
| `DB_POOL_TIMEOUT` | `30` | Segundos de espera antes de lanzar error si el pool está lleno |
| `DB_ECHO` | `false` | Si es `true`, SQLAlchemy imprime todas las queries en stdout |

#### Celery (`src/infrastructure/celery/config.py`, `docker-compose.yml`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | URL del broker Redis |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` | URL del backend de resultados |
| `CELERY_CONCURRENCY` | `4` | Número de workers de Celery ejecutándose en paralelo |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | `1` | Cuántas tareas reserva cada worker por adelantado |

#### Procesamiento de CSV (`src/infrastructure/celery/tasks.py`, `src/infrastructure/web/routers/upload.py`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `CHUNK_SIZE` | `1000` | Cantidad de filas que cada tarea Celery procesa en un batch |
| `MAX_FILE_SIZE` | `104857600` | Tamaño máximo de archivo en bytes (default: 100 MB) |

> **Tip:** Si subís un CSV de 10.000 filas con `CHUNK_SIZE=1000`, se crearán 10 tareas Celery. Con `CHUNK_SIZE=100`, se crearán 100 tareas (más granularidad, más overhead).

#### API — Uvicorn (`start-app.sh`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `UVICORN_HOST` | `0.0.0.0` | Interface de red donde escucha la API |
| `UVICORN_PORT` | `8000` | Puerto de la API |
| `UVICORN_WORKERS` | `2` | Número de procesos workers de Uvicorn |
| `UVICORN_RELOAD` | `false` | Solo desarrollo: recarga automática al detectar cambios |

> **Tip:** Para máquinas con muchas CPUs, subí `UVICORN_WORKERS` a `4` y `CELERY_CONCURRENCY` a `8` para aprovechar el hardware.

#### Storage (`src/infrastructure/storage/local_file_storage.py`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `UPLOAD_BASE_DIR` | `/tmp/procesador_csv/uploads` | Directorio donde se guardan temporalmente los CSV subidos |

### Ejemplo: override rápido desde la línea de comandos

```bash
# Levantar con más workers de Celery y chunks más pequeños
CELERY_CONCURRENCY=8 CHUNK_SIZE=500 docker compose up -d
```

### Ejemplo: usando un archivo `.env`

Crea un archivo `.env` en la raíz del proyecto:

```bash
# .env
CHUNK_SIZE=500
MAX_FILE_SIZE=52428800
CELERY_CONCURRENCY=8
UVICORN_WORKERS=4
DB_POOL_SIZE=10
```

Luego levantá los servicios normalmente:

```bash
docker compose up -d
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
