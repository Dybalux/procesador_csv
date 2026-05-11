"""Test end-to-end de flujo completo.

Crea un CSV temporal, ejecuta UploadCSV y ProcessChunk con
PostgreSQL real via testcontainers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from application.use_cases.process_chunk import ProcessChunk
from application.use_cases.upload_csv import UploadCSV
from domain.entities import TaskStatus
from domain.validation_rules import DateRule, EmailRule, UrlRule
from infrastructure.db.repositories import (
    SQLAlchemyCustomerRepository,
    SQLAlchemyErrorRepository,
    SQLAlchemyTaskRepository,
)
from infrastructure.db.uow import SQLAlchemyUnitOfWork
from infrastructure.storage.csv_mappers import CUSTOMERS_100_MAP
from infrastructure.storage.local_file_storage import LocalFileStorage


class TestFullFlow:
    def test_full_flow_valid_customers(
        self, db_engine: Any, file_storage: LocalFileStorage, db_session: Session
    ) -> None:
        csv_content = (
            b"Email,Subscription Date,Website\n"
            b"alice@example.com,2024-01-15,https://alice.com\n"
            b"bob@example.com,2024-02-20,https://bob.dev\n"
            b"charlie@example.com,2024-03-10,https://charlie.org\n"
        )
        file_path = file_storage.save("customers.csv", csv_content)

        task_repo = SQLAlchemyTaskRepository(db_session)
        upload = UploadCSV(file_storage, task_repo)
        task_id = upload(csv_content, "customers.csv")
        db_session.commit()  # Asegurar que la tarea se guarde

        # Refrescar para obtener el objeto actualizado
        db_session.refresh(task_repo.get(task_id))

        # Ajustar total_rows para que ProcessChunk transicione a COMPLETED
        task = task_repo.get(task_id)
        assert task is not None
        task.total_rows = 3
        task_repo.save(task)
        db_session.commit()

        rows = file_storage.read_chunk(
            file_path, chunk_size=1000, offset=0, header_mapping=CUSTOMERS_100_MAP
        )
        uow = SQLAlchemyUnitOfWork(session_factory=sessionmaker(bind=db_engine))
        customer_repo = SQLAlchemyCustomerRepository(uow.session, task_id=task_id)
        error_repo = SQLAlchemyErrorRepository(uow.session)
        task_repo_uow = SQLAlchemyTaskRepository(uow.session)
        rules = [EmailRule(), UrlRule(), DateRule()]
        process = ProcessChunk(task_repo_uow, customer_repo, error_repo, uow, rules)
        result = process(task_id, rows, 0)

        assert result.valid_count == 3
        assert result.error_count == 0

        # Verificar en la misma sesión de UoW
        final_task = task_repo_uow.get(task_id)
        assert final_task is not None
        assert final_task.status == TaskStatus.COMPLETED
        assert final_task.processed_rows == 3
        assert customer_repo.count_by_task(task_id) == 3
        assert len(error_repo.list_by_task(task_id)) == 0

    def test_full_flow_with_errors(
        self, db_engine: Any, file_storage: LocalFileStorage, db_session: Session
    ) -> None:
        csv_content = (
            b"Email,Subscription Date,Website\n"
            b"bad-email,2024-01-15,https://example.com\n"
            b"bob@example.com,not-a-date,https://bob.dev\n"
            b"charlie@example.com,2024-03-10,https://charlie.org\n"
        )
        file_path = file_storage.save("mixed.csv", csv_content)

        task_repo = SQLAlchemyTaskRepository(db_session)
        upload = UploadCSV(file_storage, task_repo)
        task_id = upload(csv_content, "mixed.csv")
        db_session.commit()

        task = task_repo.get(task_id)
        assert task is not None
        task.total_rows = 3
        task_repo.save(task)
        db_session.commit()

        rows = file_storage.read_chunk(
            file_path, chunk_size=1000, offset=0, header_mapping=CUSTOMERS_100_MAP
        )
        uow = SQLAlchemyUnitOfWork(session_factory=sessionmaker(bind=db_engine))
        customer_repo = SQLAlchemyCustomerRepository(uow.session, task_id=task_id)
        error_repo = SQLAlchemyErrorRepository(uow.session)
        task_repo_uow = SQLAlchemyTaskRepository(uow.session)
        rules = [EmailRule(), UrlRule(), DateRule()]
        process = ProcessChunk(task_repo_uow, customer_repo, error_repo, uow, rules)
        result = process(task_id, rows, 0)

        assert result.valid_count == 1
        assert result.error_count == 2

        final_task = task_repo_uow.get(task_id)
        assert final_task is not None
        assert final_task.status == TaskStatus.COMPLETED
        assert final_task.processed_rows == 3
        assert customer_repo.count_by_task(task_id) == 1
        assert len(error_repo.list_by_task(task_id)) == 2
