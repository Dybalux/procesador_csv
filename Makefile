.PHONY: help up down logs shell-app shell-worker test lint migrate

# ── Variables ──────────────────────────────────────────────────────────────────
COMPOSE = docker compose

# ── Default ────────────────────────────────────────────────────────────────────
help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Ciclo de vida ──────────────────────────────────────────────────────────────
up: ## Levantar todos los servicios en background
	$(COMPOSE) up -d --build

down: ## Bajar todos los servicios y eliminar contenedores
	$(COMPOSE) down

logs: ## Ver logs de todos los servicios (Ctrl+C para salir)
	$(COMPOSE) logs -f

logs-app: ## Ver logs solo de la app
	$(COMPOSE) logs -f app

logs-worker: ## Ver logs solo del worker Celery
	$(COMPOSE) logs -f worker

# ── Shells ──────────────────────────────────────────────────────────────────────
shell-app: ## Abrir shell interactivo en el contenedor app
	$(COMPOSE) exec app sh

shell-worker: ## Abrir shell interactivo en el contenedor worker
	$(COMPOSE) exec worker sh

# ── Testing ────────────────────────────────────────────────────────────────────
test: ## Correr todos los tests unitarios (sin infraestructura)
	$(COMPOSE) exec app python -m pytest src/tests/unit -v

test-integration: ## Correr tests de integración (requiere DB)
	$(COMPOSE) exec app python -m pytest src/tests/integration -v

test-e2e: ## Correr tests end-to-end (requiere servicios activos)
	$(COMPOSE) exec app python -m pytest src/tests/e2e -v

test-all: ## Correr todos los tests
	$(COMPOSE) exec app python -m pytest src/tests -v

# ── Calidad ────────────────────────────────────────────────────────────────────
lint: ## Verificar estilo de código con ruff
	$(COMPOSE) exec app python -m ruff check src/

lint-fix: ## Auto-corregir errores de estilo con ruff
	$(COMPOSE) exec app python -m ruff check --fix src/

# ── Base de datos ──────────────────────────────────────────────────────────────
migrate: ## Aplicar migraciones Alembic pendientes
	$(COMPOSE) exec app alembic upgrade head

migrate-new: ## Crear nueva migración (uso: make migrate-new MSG="descripcion")
	$(COMPOSE) exec app alembic revision --autogenerate -m "$(MSG)"

migrate-history: ## Ver historial de migraciones
	$(COMPOSE) exec app alembic history
