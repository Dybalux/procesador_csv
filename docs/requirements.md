# 📋 Requirements Guide: Asynchronous CSV Processor

## 🎯 Project Objective
Build a robust backend application to process large CSV files (specifically the "Customers" dataset). The system must demonstrate good architectural practices, efficient memory management via chunked reading, background task execution, and strict data validation.

## 🏗️ Tech Stack
- **API Framework:** FastAPI (Python)
- **Message Broker / Task Queue:** Celery + Redis
- **Database:** PostgreSQL
- **Data Validation:** Pydantic
- **Local Infrastructure:** Docker and Docker Compose

## ✅ Functional Requirements

1. **File Upload (`POST /api/v1/upload`)**
   - The system must accept a CSV file.
   - It must temporarily save the file and enqueue the processing task.
   - It must **immediately** return a `task_id` (HTTP 202 Accepted) without waiting for the file to be processed.

2. **Status Check (`GET /api/v1/tasks/{task_id}`)**
   - The user must be able to check the current processing status using the `task_id`.
   - Possible statuses: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`.

3. **Processing and Validation (Celery Worker)**
   - The system must process the CSV in **blocks (chunks)** to avoid saturating RAM.
   - Every row must be strictly validated:
     - `Email`: Valid email format.
     - `Website`: Valid URL format.
     - `Subscription Date`: Valid date.
   - **Fault Tolerance:** If a row is invalid, the process DOES NOT stop. The row is ignored, and the error is logged.

4. **Data Persistence**
   - Valid records are saved in the main data table (`customers`).
   - Invalid records are saved in a `validation_errors` table detailing the `task_id`, the row number, the original data, and the failure reason.

## 🚀 Non-Functional Requirements (Quality and Design)
- **Clean Architecture:** Clear separation between the network layer (Routers), business rules (Services), asynchronous tasks (Workers), and data access (Repositories).
- **Efficiency:** Controlled memory consumption regardless of the CSV size.
- **Resilience:** Exception handling and database connection drops managed without crashing the main API.
