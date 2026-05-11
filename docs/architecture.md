# Architecture Decisions — CSV Processor

Lightweight Architecture Decision Records (ADR-lite). Each section answers the question: **why this and not something else?**

---

## 1. Hexagonal Architecture (Ports & Adapters)

**Decision:** The domain lives in `src/domain/` without importing any frameworks.

**Problem:** In projects where FastAPI, SQLAlchemy, and Pydantic are mixed directly with business logic, changing an ORM or a framework means rewriting everything. Business rules become tied to infrastructure decisions.

**Solution:** Separate into three layers with a strict dependency rule:

```text
domain ← application ← infrastructure
```

- `domain` imports nothing external.
- `application` only imports `domain`.
- `infrastructure` imports `application` and `domain`, and can use frameworks.

**Practical consequence:** All business logic can be tested without spinning up a database or HTTP server. Unit tests run in milliseconds.

**Discarded alternative:** Traditional layered architecture (Controller → Service → Repository with inheritance). The problem is that the `Service` ends up directly importing the ORM, coupling business to infrastructure.

---

## 2. `typing.Protocol` instead of abstract classes for ports

**Decision:** `CustomerRepository`, `FileStorage`, `UnitOfWork`, etc. are `Protocol`s, not `ABC`s.

**Problem:** With `ABC`s, implementations must explicitly inherit. That's structural coupling: infrastructure knows the domain contract via inheritance.

**Solution:** `Protocol` allows for structural duck typing. Any class that implements the correct methods satisfies the contract, without needing an explicit `import` from the domain.

```python
# Test fakes DO NOT import domain protocols
class FakeTaskRepository:
    def get(self, task_id: UUID) -> ProcessingTask | None: ...
    def save(self, task: ProcessingTask) -> None: ...
```

**Practical consequence:** Testing fakes are simple Python classes. No inheritance, no `super()`, no cross dependencies.

---

## 3. Immutable Value Objects for Email, Url and SubscriptionDate

**Decision:** Validated domain fields are value objects with `@dataclass(frozen=True)`, not primitive strings.

**Problem:** If `email` is a `str`, any part of the code can assign `"this is not an email"` to it, and the error will be discovered late, in production.

**Solution:** Encapsulate the format and validity rules within the type. An invalid `Email` cannot exist — it fails on construction.

```python
email = Email("not-an-email")  # → ValidationFailed in __post_init__
```

**Practical consequence:** If you hold an `Email` object, it's already validated. You don't need to re-validate it in every function that receives it.

**Discarded alternative:** Direct Pydantic validators on the entity. The problem is that it introduces a Pydantic dependency into the domain, violating the dependency rule.

---

## 4. Explicit State Machine in `ProcessingTask`

**Decision:** State transitions (`PENDING → PROCESSING → COMPLETED | FAILED`) are encoded as a valid transitions table in the domain.

**Problem:** Without a state machine, any code can do `task.status = "COMPLETED"`, skipping the correct flow. State bugs are hard to track down.

**Solution:** `transition_to()` validates against `_VALID_TRANSITIONS` and raises `ValidationFailed` if the transition is illegal.

```python
# PENDING cannot go straight to COMPLETED
task.transition_to(TaskStatus.COMPLETED)  # → ValidationFailed
```

**Practical consequence:** It is impossible for a task to transition to `COMPLETED` without having gone through `PROCESSING`. An incorrect flow results in a runtime error, not a silent bug.

---

## 5. Unit of Work as a context manager

**Decision:** `UnitOfWork` is a `Protocol` with `__enter__` / `__exit__` and explicit `commit()` / `rollback()`.

**Problem:** If `CustomerRepository.add_bulk()` and `ErrorRepository.add_bulk()` use independent transactions, they can end up in an inconsistent state if one fails halfway through.

**Solution:** Both operations occur within the same `with uow:`. The `__exit__` method performs an automatic rollback if it exits with an exception.

```python
with self._uow:
    self._customer_repo.add_bulk(valid)
    self._error_repo.add_bulk(errors)
    self._task_repo.save(task)
    self._uow.commit()
# If anything fails → automatic rollback. Atomicity guaranteed.
```

**Practical consequence:** You will never have an updated `customers` table and an outdated `processing_tasks` table.

---

## 6. Strategy Pattern for validation rules

**Decision:** `EmailRule`, `UrlRule`, and `DateRule` are separate classes that implement the same `ValidationRule` Protocol.

**Problem:** A `validate_row()` function with 15 ifs becomes unmaintainable. Adding a new rule means modifying the existing function (Open/Closed violation).

**Solution:** Each rule is a class. Adding a new rule = creating a new class. `ProcessChunk` receives the list of rules via its constructor (dependency injection).

```python
# Adding phone validation doesn't touch ProcessChunk
rules = [EmailRule(), UrlRule(), DateRule(), PhoneRule()]
```

**Practical consequence:** Rules are testable in isolation. Application order is configurable.

---

## 7. Celery with independent chunks instead of a single task per file

**Decision:** Each CSV chunk is a separate Celery task, rather than a single task processing the entire file.

**Problem:** A single task processing 100,000 rows takes minutes. If the worker crashes halfway through, all work is lost and must be restarted from scratch.

**Solution:** Divide the file into N chunks of `CHUNK_SIZE` rows. Each chunk is an independent task with automatic retries.

```text
File with 10,000 rows, CHUNK_SIZE=1000
→ 10 independent Celery tasks
→ If chunk 5 fails → only chunk 5 is retried
→ Chunks 1-4 are already persisted
```

**Practical consequence:** Resilience against worker failures. Real parallelism: multiple workers process different chunks simultaneously.

**Tradeoff:** Higher Redis overhead (N messages instead of 1). For small files (<1000 rows), the overhead is irrelevant; for large files, the benefits outweigh the costs.

---

## 8. Separation of FileStorage and database

**Decision:** CSV files are saved to disk (`/tmp/procesador_csv/uploads`), not in PostgreSQL. The DB only stores metadata and processed data.

**Problem:** Saving large binary files in PostgreSQL is possible but inefficient. It bloats the DB size, complicates backups, and the ORM is not optimized for streaming binaries.

**Solution:** The file lives on the filesystem, the DB stores the `file_path`. The `FileStorage` port abstracts the storage medium — it could be local filesystem, S3, GCS, etc.

**Practical consequence:** Migrating from local storage to S3 means implementing a new class that satisfies the `FileStorage` Protocol. Business logic remains unchanged.

---

## 9. `create_app()` as a factory instead of module-level

**Decision:** The FastAPI application is created inside a `create_app()` function, not as a global module variable.

**Problem:** A global FastAPI instance makes it hard to test with different configurations (e.g., SQLite in tests, PostgreSQL in production). Test `dependency_overrides` become harder to manage.

**Solution:** `create_app()` allows instantiating the app multiple times with different configurations. Uvicorn invokes it with `--factory`.

**Practical consequence:** Router tests can create their own instance with overrides without affecting other instances.

---

## 10. Health check with active dependency checks

**Decision:** `GET /api/v1/health` executes `SELECT 1` against PostgreSQL and `PING` against Redis on every request.

**Problem:** A health check that only returns `{"status": "ok"}` won't detect if the DB is down. The load balancer will consider it healthy and keep routing traffic to an app that can't persist anything.

**Solution:** Active checks with a short timeout (2 seconds). If any fails → HTTP 503. The load balancer pulls the pod out of rotation.

**Tradeoff:** Every request to `/health` generates a DB query and a Redis connection. To avoid overload, configure the load balancer health check with a minimum interval of 10-30 seconds, not 1 second.

**Celery Workers:** Not checked on this endpoint. Determining if a worker is alive requires `celery inspect ping`, which has variable latency and can block. Worker availability is monitored at the infrastructure level (Flower, Celery metrics).
