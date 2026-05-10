# 📋 Guía de Requerimientos: Procesador de CSV Asíncrono

## 🎯 Objetivo del Proyecto
Construir una aplicación backend robusta para procesar archivos CSV pesados (específicamente el dataset de "Customers"). El sistema debe demostrar buenas prácticas de arquitectura, manejo eficiente de memoria mediante lectura por chunks, ejecución de tareas en segundo plano y validación estricta de datos.

## 🏗️ Stack Tecnológico
- **API Framework:** FastAPI (Python)
- **Message Broker / Cola de Tareas:** Celery + Redis
- **Base de Datos:** PostgreSQL
- **Validación de Datos:** Pydantic
- **Infraestructura Local:** Docker y Docker Compose

## ✅ Requerimientos Funcionales

1. **Subida de Archivos (`POST /api/v1/upload`)**
   - El sistema debe recibir un archivo CSV.
   - Debe guardar el archivo temporalmente y encolar la tarea.
   - Debe devolver un `task_id` (HTTP 202 Accepted) de forma **inmediata** sin esperar a que el archivo sea procesado.

2. **Consulta de Estado (`GET /api/v1/tasks/{task_id}`)**
   - El usuario debe poder consultar el estado actual del procesamiento usando el `task_id`.
   - Estados posibles: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`.

3. **Procesamiento y Validación (Worker Celery)**
   - El sistema debe procesar el CSV **por bloques (chunks)** para no saturar la memoria RAM.
   - Cada fila se validará estrictamente:
     - `Email`: Formato de correo válido.
     - `Website`: Formato de URL válido.
     - `Subscription Date`: Fecha válida.
   - **Tolerancia a fallos:** Si una fila es inválida, el proceso NO se detiene. Se ignora la fila y el error se registra.

4. **Persistencia de Datos**
   - Los registros válidos se guardan en la tabla principal de datos (`customers`).
   - Los registros inválidos se guardan en una tabla de `validation_errors` detallando el `task_id`, el número de fila, los datos originales y el motivo del fallo.

## 🚀 Requerimientos No Funcionales (Calidad y Diseño)
- **Arquitectura Limpia:** Separación clara entre la capa de red (Routers), reglas de negocio (Services), tareas asíncronas (Workers) y acceso a datos (Repositories).
- **Eficiencia:** Consumo de memoria controlado independientemente del tamaño del CSV.
- **Resiliencia:** Manejo de excepciones y caídas de base de datos sin crashear la API principal.
