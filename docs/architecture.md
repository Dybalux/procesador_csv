# Decisiones de Arquitectura — Procesador CSV

Documento de registro de decisiones técnicas (ADR-lite). Cada sección responde a la pregunta: **¿por qué esto y no otra cosa?**

---

## 1. Arquitectura Hexagonal (Ports & Adapters)

**Decisión:** El dominio vive en `src/domain/` sin importar ningún framework.

**Problema:** En proyectos donde FastAPI, SQLAlchemy y Pydantic se mezclan directamente con la lógica de negocio, cambiar un ORM o un framework implica reescribir todo. Las reglas de negocio quedan atadas a decisiones de infraestructura.

**Solución:** Separar en tres capas con regla de dependencia estricta:

```
domain ← application ← infrastructure
```

- `domain` no importa nada externo
- `application` importa solo `domain`
- `infrastructure` importa `application` y `domain`, y puede usar frameworks

**Consecuencia práctica:** Se puede testear toda la lógica de negocio sin levantar base de datos ni servidor HTTP. Los tests unitarios corren en milisegundos.

**Alternativa descartada:** Arquitectura en capas tradicional (Controller → Service → Repository con herencia). El problema es que `Service` termina importando ORM directamente, acoplando negocio a infraestructura.

---

## 2. `typing.Protocol` en lugar de clases abstractas para los puertos

**Decisión:** `CustomerRepository`, `FileStorage`, `UnitOfWork`, etc. son `Protocol`, no `ABC`.

**Problema:** Con `ABC`, las implementaciones deben heredar explícitamente. Eso es acoplamiento estructural: la infra conoce el contrato del dominio vía herencia.

**Solución:** `Protocol` permite duck typing estructural. Cualquier clase que implemente los métodos correctos satisface el contrato, sin necesidad de `import` explícito desde el dominio.

```python
# Las fakes de tests NO importan los protocolos del dominio
class FakeTaskRepository:
    def get(self, task_id: UUID) -> ProcessingTask | None: ...
    def save(self, task: ProcessingTask) -> None: ...
```

**Consecuencia práctica:** Los fakes de testing son simples clases Python. Sin herencia, sin `super()`, sin dependencias cruzadas.

---

## 3. Value Objects inmutables para Email, Url y SubscriptionDate

**Decisión:** Los campos validados del dominio son value objects con `@dataclass(frozen=True)`, no strings primitivos.

**Problema:** Si `email` es un `str`, cualquier parte del código puede asignarle `"esto no es un email"` y el error se descubre tarde, en producción.

**Solución:** Encapsular el formato y las reglas de validez dentro del tipo. Un `Email` inválido no puede existir — falla en construcción.

```python
email = Email("no-es-un-email")  # → ValidationFailed en __post_init__
```

**Consecuencia práctica:** Si tenés un `Email` en mano, ya está validado. No necesitás re-validar en cada función que lo recibe.

**Alternativa descartada:** Pydantic validators directo en la entidad. El problema es que introduce dependencia de Pydantic en el dominio, violando la regla de dependencia.

---

## 4. State Machine explícita en `ProcessingTask`

**Decisión:** Las transiciones de estado (`PENDING → PROCESSING → COMPLETED | FAILED`) están codificadas como tabla de transiciones válidas en el dominio.

**Problema:** Sin máquina de estados, cualquier código puede hacer `task.status = "COMPLETED"` saltando el flujo correcto. Los bugs de estado son difíciles de rastrear.

**Solución:** `transition_to()` valida contra `_VALID_TRANSITIONS` y lanza `ValidationFailed` si la transición es ilegal.

```python
# PENDING no puede ir directo a COMPLETED
task.transition_to(TaskStatus.COMPLETED)  # → ValidationFailed
```

**Consecuencia práctica:** Es imposible que una tarea pase a `COMPLETED` sin haber pasado por `PROCESSING`. El flujo incorrecto es un error en tiempo de ejecución, no un bug silencioso.

---

## 5. Unit of Work como context manager

**Decisión:** `UnitOfWork` es un `Protocol` con `__enter__` / `__exit__` y `commit()` / `rollback()` explícito.

**Problema:** Si `CustomerRepository.add_bulk()` y `ErrorRepository.add_bulk()` usan transacciones independientes, pueden quedar en estado inconsistente si una de las dos falla a mitad.

**Solución:** Ambas operaciones ocurren dentro del mismo `with uow:`. El `__exit__` hace rollback automático si sale por excepción.

```python
with self._uow:
    self._customer_repo.add_bulk(valid)
    self._error_repo.add_bulk(errors)
    self._task_repo.save(task)
    self._uow.commit()
# Si algo falla → rollback automático. Atomicidad garantizada.
```

**Consecuencia práctica:** Nunca queda la tabla `customers` actualizada y la tabla `processing_tasks` sin actualizar.

---

## 6. Strategy Pattern para reglas de validación

**Decisión:** `EmailRule`, `UrlRule` y `DateRule` son clases separadas que implementan el mismo `ValidationRule` Protocol.

**Problema:** Una función `validate_row()` con 15 ifs se vuelve inmantenible. Agregar una nueva regla implica modificar la función existente (violación de Open/Closed).

**Solución:** Cada regla es una clase. Agregar una regla nueva = crear una clase nueva. `ProcessChunk` recibe la lista de reglas por constructor (inyección de dependencias).

```python
# Agregar validación de teléfono no toca ProcessChunk
rules = [EmailRule(), UrlRule(), DateRule(), PhoneRule()]
```

**Consecuencia práctica:** Las reglas son testeables de forma aislada. El orden de aplicación es configurable.

---

## 7. Celery con chunks independientes en lugar de un task por archivo

**Decisión:** Cada chunk del CSV es una tarea Celery separada, no un único task que procesa todo el archivo.

**Problema:** Un task único que procesa 100.000 filas tarda minutos. Si el worker se cae a mitad, se pierde todo el trabajo y hay que reiniciar desde cero.

**Solución:** Dividir el archivo en N chunks de `CHUNK_SIZE` filas. Cada chunk es una tarea independiente con retry automático.

```
Archivo de 10.000 filas, CHUNK_SIZE=1000
→ 10 tareas Celery independientes
→ Si el chunk 5 falla → solo se reintenta el chunk 5
→ Los chunks 1-4 ya están persistidos
```

**Consecuencia práctica:** Resiliencia ante fallos del worker. Paralelismo real: múltiples workers procesan diferentes chunks simultáneamente.

**Tradeoff:** Mayor overhead de Redis (N mensajes en lugar de 1). Para archivos pequeños (<1000 filas) el overhead es irrelevante; para archivos grandes el beneficio supera el costo.

---

## 8. Separación de FileStorage y base de datos

**Decisión:** Los archivos CSV se guardan en disco (`/tmp/procesador_csv/uploads`), no en PostgreSQL. La DB solo almacena metadatos y datos procesados.

**Problema:** Guardar archivos binarios grandes en PostgreSQL es posible pero ineficiente. Aumenta el tamaño de la DB, complica backups, y el ORM no está optimizado para streaming de binarios.

**Solución:** El archivo vive en el filesystem, la DB guarda el `file_path`. El port `FileStorage` abstrae el medio de almacenamiento — puede ser filesystem local, S3, GCS, etc.

**Consecuencia práctica:** Migrar de almacenamiento local a S3 implica implementar una nueva clase que satisfaga el `FileStorage` Protocol. La lógica de negocio no cambia.

---

## 9. `create_app()` como factory en lugar de módulo-level

**Decisión:** La aplicación FastAPI se crea dentro de una función `create_app()`, no como variable global del módulo.

**Problema:** Una instancia global de FastAPI hace difícil testear con configuraciones distintas (ej: SQLite en tests, PostgreSQL en producción). Los `dependency_overrides` en tests son más complicados de manejar.

**Solución:** `create_app()` permite instanciar la app múltiples veces con configuraciones distintas. Uvicorn la invoca con `--factory`.

**Consecuencia práctica:** Los tests de routers pueden crear su propia instancia con overrides sin afectar otras instancias.

---

## 10. Health check con chequeo activo de dependencias

**Decisión:** `GET /api/v1/health` ejecuta `SELECT 1` contra PostgreSQL y `PING` contra Redis en cada request.

**Problema:** Un health check que solo retorna `{"status": "ok"}` no detecta si la DB está caída. El load balancer lo considera sano y sigue enrutando tráfico a una app que no puede persistir nada.

**Solución:** Chequeos activos con timeout corto (2 segundos). Si alguno falla → HTTP 503. El load balancer saca el pod del rotation.

**Tradeoff:** Cada request a `/health` genera una query a DB y una conexión a Redis. Para evitar sobrecarga, configurar el health check del load balancer con intervalo mínimo de 10-30 segundos, no 1 segundo.

**Workers de Celery:** No se chequean en este endpoint. Determinar si un worker está vivo requiere `celery inspect ping`, que tiene latencia variable y puede bloquear. La disponibilidad de workers se monitorea a nivel de infraestructura (Flower, métricas de Celery).
