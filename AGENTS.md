# AGENTS.md — Procesador CSV

Instrucciones para agentes AI que trabajen en este proyecto.

---

## Stack & Tecnología

| Capa | Tecnología |
|------|------------|
| Web Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (modo `Mapped[]` + `mapped_column()`) |
| Async Tasks | Celery + Redis |
| Database | PostgreSQL |
| Testing | pytest + testcontainers |
| Lint/Format | ruff + mypy |
| Migrations | Alembic |

---

## Arquitectura: Hexagonal / Clean Architecture

```
src/
├── domain/           # Entidades y puertos (puro, sin frameworks)
│   ├── models/       # Entidades de negocio
│   └── ports/        # Interfaces (FileStorage, TaskRepository)
├── application/      # Casos de uso
│   └── use_cases/    # Lógica de negocio orquestada
├── infrastructure/   # Adaptadores (frameworks, DB, Celery)
│   ├── db/           # SQLAlchemy models, connection
│   ├── celery/       # Tasks y config
│   ├── storage/      # FileStorage implementation
│   └── web/          # FastAPI app, dependencies
└── api/              # Routers organizados jerárquicamente
    ├── __init__.py   # api_router con prefix /api
    └── v1/
        ├── __init__.py  # v1_router con prefix /v1
        └── endpoints/   # upload, tasks, health
```

### Reglas de dependencias (CRÍTICO)

```
domain → (nada, es puro)
application → domain
infrastructure → application, domain
api → infrastructure, application, domain
```

**NUNCA** importar `infrastructure` desde `domain` o `application`.

---

## Routing Hierarchy

```
main.py
├── /health           → health.router (sin prefix)
└── /api              → api_router
    └── /v1           → v1_router
        ├── /upload   → upload.router
        └── /tasks    → tasks.router
```

Rutas finales:
- `GET /health` — Health check directo
- `POST /api/v1/upload` — Subida de CSV
- `GET /api/v1/tasks/{task_id}` — Estado de tarea

---

## SQLAlchemy 2.0 Style (OBLIGATORIO)

```python
# ✅ CORRECTO
from sqlalchemy.orm import Mapped, mapped_column

class Task(Base):
    __tablename__ = "tasks"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime)

# ❌ INCORRECTO (estilo 1.x)
id = Column(Integer, primary_key=True)
```

---

## Testing

### Estructura de tests
```
src/tests/
├── unit/             # Tests aislados (sin DB)
├── integration/      # Con PostgreSQL real via testcontainers
└── e2e/             # Full flow API → DB → Celery
```

### Comandos
```bash
# Todos los tests (requiere Docker)
pytest

# Solo unitarios
pytest src/tests/unit/

# Con cobertura
pytest --cov=src --cov-report=term-missing
```

### Database en tests
- Usar **testcontainers** para PostgreSQL real
- Nunca SQLite (ya migramos todo a PostgreSQL)
- Ver `src/tests/integration/conftest.py` para fixtures

---

## Comandos útiles

```bash
# Levantar todo (app + db + redis + worker)
docker-compose up

# Migraciones
alembic revision --autogenerate -m "description"
alembic upgrade head

# Linting y types
ruff check .
mypy src/

# Celery worker (local, sin Docker)
celery -A infrastructure.celery.app worker --loglevel=info
```

---

## Convenciones de código

- **Imports**: `from __future__ import annotations` siempre
- **Tipado**: Type hints obligatorios, sin `Any` implícito
- **Docstrings**: Google style o compacto, pero consistente
- **Commits**: Conventional commits, en inglés, sin "Co-Authored-By"
- **Idioma**: Código y commits en inglés, docs pueden ser en español

---

## Decisiones de diseño importantes

1. **Chunking**: CSV se procesa en chunks de 100 filas (`settings.CHUNK_SIZE`)
2. **Async tasks**: Cada chunk se encola como task Celery separada
3. **File storage**: Local en `/app/uploads` (volume compartido app-worker)
4. **Health check**: Verifica PostgreSQL + Redis, retorna 503 si algo falla
5. **Dominio puro**: Entidades no dependen de SQLAlchemy (ver `domain/models/task.py` vs `infrastructure/db/models.py`)

---

## Files clave para entender el flujo

| File | Propósito |
|------|-----------|
| `src/domain/models/task.py` | Entidad de dominio pura |
| `src/application/use_cases/upload_csv.py` | Caso de uso: subir CSV |
| `src/infrastructure/celery/tasks.py` | Task que procesa chunks |
| `src/api/v1/endpoints/upload.py` | Endpoint HTTP |
| `src/tests/e2e/test_full_flow.py` | Test E2E completo |

---

## Contacto / Contexto

- Proyecto de aprendizaje de Clean Architecture en Python
- Autor: Lagoria Luciano <lagorialuciano@gmail.com>
- Repo: https://github.com/Dybalux/procesador_csv
