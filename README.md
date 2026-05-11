# Asynchronous CSV Processor

A CSV file processor built with a clean/hexagonal architecture. It supports large files, background chunk processing with Celery, and persistence in PostgreSQL.

## 🏗️ Architecture

**Hexagonal Architecture (Ports & Adapters)** with the following layers:

```text
src/
├── domain/              # Domain layer (pure Python)
│   ├── entities.py      # Business entities
│   ├── value_objects.py # Email, Url, SubscriptionDate
│   ├── exceptions.py    # Domain exceptions
│   ├── ports.py         # Protocols (interfaces)
│   └── validation_rules.py # Validation rules
│
├── application/         # Use cases
│   ├── use_cases/       # UploadCSV, GetTaskStatus, ProcessChunk
│   └── interfaces.py    # DTOs (Pydantic)
│
└── infrastructure/      # Adapters
    ├── db/              # SQLAlchemy + PostgreSQL
    ├── storage/         # Local FileSystem
    ├── celery/          # Workers + Redis
    └── web/             # FastAPI + routers
```

**Key Principle:** The domain MUST NOT import frameworks (FastAPI, Celery, SQLAlchemy, Pydantic).

## 📖 Use Cases

The application layer exposes three main use cases that orchestrate the entire CSV processing flow.

### `UploadCSV` — Upload a CSV file

**Responsibility:** Receives the content of a CSV file, persists it to disk, creates a processing task in `PENDING` state, and automatically enqueues all chunks in Celery for background processing.

**Input:**
- `file_content` (bytes): file content
- `filename` (str): original filename

**Output:**
- `task_id` (UUID): unique identifier of the created task

**Internal flow:**
```text
Validates .csv extension and max size
    → Saves file to disk via FileStorage
    → Creates ProcessingTask(status=PENDING)
    → Persists task via TaskRepository
    → Counts CSV rows
    → Enqueues N Celery tasks (one per chunk)
    → Returns task_id
```

**Endpoint:** `POST /api/v1/upload`

---

### `GetTaskStatus` — Check task status

**Responsibility:** Fetches a processing task by its ID and returns a DTO with its current status, processed rows, total rows, and creation date.

**Input:**
- `task_id` (UUID): task identifier

**Output:**
- `TaskStatusDTO`: `{ status, processed_rows, total_rows, created_at }`

**Exceptions:**
- `TaskNotFound`: if the task does not exist in the database

**Internal flow:**
```text
Receives task_id
    → Fetches task via TaskRepository.get()
    → If not exists → raises TaskNotFound
    → Maps to TaskStatusDTO
    → Returns DTO
```

**Endpoint:** `GET /api/v1/tasks/{task_id}`

---

### `ProcessChunk` — Process a batch of CSV rows

**Responsibility:** Processes a chunk of CSV rows by applying validation rules in order, separating valid from invalid rows, bulk persisting both within an atomic unit of work, and updating the task's processed rows counter.

**Input:**
- `task_id` (UUID): parent task identifier
- `rows` (list[dict]): list of rows in the chunk
- `chunk_offset` (int): starting row number (to calculate actual row_number)

**Output:**
- `ChunkResult`: `{ valid_count, error_count }`

**Internal flow:**
```text
Receives task_id + rows + chunk_offset
    → Fetches task → if not exists → raises TaskNotFound
    → If status is PENDING → transition_to(PROCESSING)
    → For each row:
        - Applies validation rules (EmailRule, UrlRule, DateRule)
        - If valid → builds Customer → valid list
        - If invalid → builds RowValidationError → errors list
    → Opens UnitOfWork
        - CustomerRepository.add_bulk(valid)
        - ErrorRepository.add_bulk(errors)
        - TaskRepository.save(task) with advance_progress()
        - If processed_rows >= total_rows → transition_to(COMPLETED)
        - commit()
    → Returns ChunkResult
```

**Executed by:** Celery Worker (background, asynchronous)

---

### 🔄 End-to-End Flow

```text
┌─────────────┐     POST /api/v1/upload      ┌─────────────┐
│    User     │ ───────────────────────────→ │   FastAPI   │
│  (Client)   │                              │   (app)     │
└─────────────┘                              └──────┬──────┘
       ↑                                            │
       │           {"task_id": "xxx"}               │
       └────────────────────────────────────────────┘

                           │
                           ▼
                    ┌──────────────┐
                    │  UploadCSV   │
                    │  - Saves     │
                    │    file      │
                    │  - Creates   │
                    │    task      │
                    │  - Enqueues  │
                    │    chunks    │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │     Redis    │
                    │   (Broker)   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    Celery    │
                    │   (worker)   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ ProcessChunk │
                    │  - Validates │
                    │  - Persists  │
                    │  - Updates   │
                    │    counter   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  PostgreSQL  │
                    │     (DB)     │
                    └──────────────┘

       GET /api/v1/tasks/{task_id}
       ─────────────────────────────→
       ←─────────────────────────────
       {"status": "PROCESSING",
        "processed_rows": 1000}
```

**Task statuses:**
- `PENDING` → task created, waiting to be processed
- `PROCESSING` → at least one chunk is being processed
- `COMPLETED` → all chunks processed (if total_rows is known)
- `FAILED` → an unrecoverable error occurred

---

## 🚀 Tech Stack

- **Python 3.11** + Alpine Linux
- **FastAPI** - REST API
- **Celery 5.6** + **Redis** - Task queue
- **PostgreSQL 15** - Database
- **SQLAlchemy 2.0** - ORM with `Mapped[]`/`mapped_column()`
- **Pydantic v2** - Validation and DTOs
- **Alembic** - DB Migrations
- **Docker + Docker Compose** - Infrastructure

## 📋 Prerequisites

- Docker Engine 24+
- Docker Compose v2+
- curl (to test the API)

## 🔧 Installation & Setup

### 1. Clone and enter the project

```bash
git clone <repo-url>
cd procesador_csv
```

### 2. Start services

```bash
# Bring down everything if previously running
docker compose down -v

# Rebuild images (first time or after changes)
docker compose build --no-cache

# Bring up services
docker compose up -d
```

### 3. Check status

```bash
docker compose ps
```

Wait to see:
- `db` → `(healthy)`
- `app` → `Up`
- `worker` → `Up`
- `redis` → `Up`

### 4. Apply migrations (first time)

```bash
# If tables don't exist, apply Alembic migration
docker compose exec app alembic upgrade head
```

## ⚙️ Configuration

All configuration is done via **environment variables** (12-factor app principle). You can modify values by editing the `docker-compose.yml` file or creating a `.env` file in the project root.

### Available variables

#### Database (`src/infrastructure/db/connection.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg2://user:pass@db/procesador_csv` | PostgreSQL connection URL |
| `DB_POOL_SIZE` | `5` | Permanent connections kept in the pool |
| `DB_MAX_OVERFLOW` | `10` | Extra connections created on demand |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait before raising an error if the pool is full |
| `DB_ECHO` | `false` | If `true`, SQLAlchemy prints all queries to stdout |

#### Celery (`src/infrastructure/celery/config.py`, `docker-compose.yml`)

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Redis broker URL |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` | Results backend URL |
| `CELERY_CONCURRENCY` | `4` | Number of Celery workers running in parallel |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | `1` | How many tasks each worker reserves in advance |

#### CSV Processing (`src/infrastructure/celery/tasks.py`, `src/api/v1/endpoints/upload.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | `1000` | Amount of rows each Celery task processes in a batch |
| `MAX_FILE_SIZE` | `104857600` | Maximum file size in bytes (default: 100 MB) |

> **Tip:** If you upload a 10,000-row CSV with `CHUNK_SIZE=1000`, 10 Celery tasks will be created. With `CHUNK_SIZE=100`, 100 tasks will be created (more granularity, more overhead).

#### API — Uvicorn (`start-app.sh`)

| Variable | Default | Description |
|----------|---------|-------------|
| `UVICORN_HOST` | `0.0.0.0` | Network interface where the API listens |
| `UVICORN_PORT` | `8000` | API Port |
| `UVICORN_WORKERS` | `2` | Number of Uvicorn worker processes |
| `UVICORN_RELOAD` | `false` | Development only: automatic reload on changes |

> **Tip:** For machines with multiple CPUs, increase `UVICORN_WORKERS` to `4` and `CELERY_CONCURRENCY` to `8` to leverage hardware.

#### Storage (`src/infrastructure/storage/local_file_storage.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `UPLOAD_BASE_DIR` | `/tmp/procesador_csv/uploads` | Directory where uploaded CSVs are temporarily stored |

### Example: Quick command-line override

```bash
# Bring up with more Celery workers and smaller chunks
CELERY_CONCURRENCY=8 CHUNK_SIZE=500 docker compose up -d
```

### Example: Using a `.env` file

Create an `.env` file in the project root:

```bash
# .env
CHUNK_SIZE=500
MAX_FILE_SIZE=52428800
CELERY_CONCURRENCY=8
UVICORN_WORKERS=4
DB_POOL_SIZE=10
```

Then start the services normally:

```bash
docker compose up -d
```

## 🎯 Usage

### Upload a CSV file

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@customers-100.csv"
```

**Response:**
```json
{"task_id": "xxxxx-xxxxx-xxxxx-xxxxx"}
```

Processing is **automatic**: the API enqueues the chunks in Celery without manual intervention.

### Check task status

```bash
curl http://localhost:8000/api/v1/tasks/YOUR_TASK_ID
```

**Response:**
```json
{
  "status": "PROCESSING",
  "processed_rows": 100,
  "total_rows": null,
  "created_at": "2026-05-11T01:45:13"
}
```

### View worker logs in real-time

```bash
docker compose logs -f worker
```

### Verify data in PostgreSQL

```bash
docker compose exec db psql -U user -d procesador_csv -c "SELECT COUNT(*) FROM customers;"
```

## 🧪 Testing

```bash
# Unit tests
docker compose exec app pytest src/tests/unit/ -v

# Integration tests
docker compose exec app pytest src/tests/integration/ -v

# E2E tests
docker compose exec app pytest src/tests/e2e/ -v

# All tests
docker compose exec app pytest
```

## 🗂️ Project Structure

```text
procesador_csv/
├── docker-compose.yml          # Services: app, worker, db, redis
├── Dockerfile                  # Multi-stage build with Alpine
├── docker-entrypoint.sh        # Entrypoint for non-root permissions
├── alembic.ini                 # Alembic configuration
├── pyproject.toml              # Dependencies & project config
├── migrations/                 # Alembic migrations
│   ├── env.py
│   └── versions/
│       └── c6b4a68c61ab_initial_migration.py
└── src/
    ├── domain/                 # Pure logic, no frameworks
    ├── application/            # Use cases
    ├── infrastructure/         # Adapters (DB, Celery, Web)
    └── tests/                  # Unit, Integration, E2E tests
```

## 🔒 Security

- Containers run as a **non-root user** (`appuser`, UID 1000).
- No Celery warnings for superuser privileges.
- Entrypoint fixes shared volume permissions before dropping privileges.

## 🐛 Key Design Decisions

1. **DB → App race condition**: PostgreSQL healthcheck with `pg_isready`. The app and worker wait for the DB to be `(healthy)` before starting.
2. **Shared volume**: `uploads_data` mounted at `/tmp/procesador_csv/uploads` for both `app` and `worker`. Without this, the worker cannot find files uploaded by the app.
3. **Automatic Celery retries**: If the worker tries to process before the upload transaction is committed, Celery performs an automatic retry (max 3 attempts, exponential backoff).
4. **Idempotency**: Each CSV row generates a unique UUID. Reprocessing a chunk does not duplicate customers.

## 📦 Database Migrations

```bash
# Automatically create new migration
docker compose exec app alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec app alembic upgrade head

# View current version
docker compose exec app alembic current
```

## 🛑 Stopping services

```bash
# Bring down preserving data
docker compose down

# Bring down deleting EVERYTHING (including DB volumes)
docker compose down -v
```

## 📝 License

MIT
