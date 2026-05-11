"""Test end-to-end de flujo completo.

Crea un CSV temporal, ejecuta UploadCSV y ProcessChunk con
infraestructura real, y verifica el estado final en la base de datos.
"""

from __future__ import annotations

import os
import sys

import pytest

from domain.entities import TaskStatus


def _make_full_flow_setup(tmp_path):
    """Reimporta infraestructura con SQLite en memoria."""
    for key in list(sys.modules.keys()):
        if key.startswith("infrastructure"):
            del sys.modules[key]
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from sqlalchemy.orm import sessionmaker

    from infrastructure.db.connection import Base, engine
    from infrastructure.storage.csv_mappers import CUSTOMERS_100_MAP
    from infrastructure.storage.local_file_storage import LocalFileStorage

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    storage = LocalFileStorage(base_dir=str(tmp_path))
    return engine, Session, storage, CUSTOMERS_100_MAP


@pytest.fixture
def full_flow_setup(tmp_path):
    engine, Session, storage, csv_map = _make_full_flow_setup(tmp_path)
    yield engine, Session, storage, csv_map


class TestFullFlow:
    def test_full_flow_valid_customers(self, full_flow_setup):
        engine, Session, storage, csv_map = full_flow_setup

        from application.use_cases.process_chunk import ProcessChunk
        from application.use_cases.upload_csv import UploadCSV
        from domain.validation_rules import DateRule, EmailRule, UrlRule
        from infrastructure.db.repositories import (
            SQLAlchemyCustomerRepository,
            SQLAlchemyErrorRepository,
            SQLAlchemyTaskRepository,
        )
        from infrastructure.db.uow import SQLAlchemyUnitOfWork

        csv_content = (
            b"Email,Subscription Date,Website\n"
            b"alice@example.com,2024-01-15,https://alice.com\n"
            b"bob@example.com,2024-02-20,https://bob.dev\n"
            b"charlie@example.com,2024-03-10,https://charlie.org\n"
        )
        file_path = storage.save("customers.csv", csv_content)

        session = Session()
        task_repo = SQLAlchemyTaskRepository(session)
        upload = UploadCSV(storage, task_repo)
        task_id = upload(csv_content, "customers.csv")

        # Ajustar total_rows para que ProcessChunk transicione a COMPLETED
        task = task_repo.get(task_id)
        task.total_rows = 3
        task_repo.save(task)
        session.commit()

        rows = storage.read_chunk(
            file_path, chunk_size=1000, offset=0, header_mapping=csv_map
        )
        uow = SQLAlchemyUnitOfWork()
        customer_repo = SQLAlchemyCustomerRepository(uow.session, task_id=task_id)
        error_repo = SQLAlchemyErrorRepository(uow.session)
        task_repo_uow = SQLAlchemyTaskRepository(uow.session)
        rules = [EmailRule(), UrlRule(), DateRule()]
        process = ProcessChunk(task_repo_uow, customer_repo, error_repo, uow, rules)
        result = process(task_id, rows, 0)

        assert result.valid_count == 3
        assert result.error_count == 0

        session2 = Session()
        task_repo2 = SQLAlchemyTaskRepository(session2)
        customer_repo2 = SQLAlchemyCustomerRepository(session2, task_id=task_id)
        error_repo2 = SQLAlchemyErrorRepository(session2)

        task = task_repo2.get(task_id)
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.processed_rows == 3
        assert customer_repo2.count_by_task(task_id) == 3
        assert len(error_repo2.list_by_task(task_id)) == 0

        session.close()
        session2.close()

    def test_full_flow_with_errors(self, full_flow_setup):
        engine, Session, storage, csv_map = full_flow_setup

        from application.use_cases.process_chunk import ProcessChunk
        from application.use_cases.upload_csv import UploadCSV
        from domain.validation_rules import DateRule, EmailRule, UrlRule
        from infrastructure.db.repositories import (
            SQLAlchemyCustomerRepository,
            SQLAlchemyErrorRepository,
            SQLAlchemyTaskRepository,
        )
        from infrastructure.db.uow import SQLAlchemyUnitOfWork

        csv_content = (
            b"Email,Subscription Date,Website\n"
            b"bad-email,2024-01-15,https://example.com\n"
            b"bob@example.com,not-a-date,https://bob.dev\n"
            b"charlie@example.com,2024-03-10,https://charlie.org\n"
        )
        file_path = storage.save("mixed.csv", csv_content)

        session = Session()
        task_repo = SQLAlchemyTaskRepository(session)
        upload = UploadCSV(storage, task_repo)
        task_id = upload(csv_content, "mixed.csv")

        task = task_repo.get(task_id)
        task.total_rows = 3
        task_repo.save(task)
        session.commit()

        rows = storage.read_chunk(
            file_path, chunk_size=1000, offset=0, header_mapping=csv_map
        )
        uow = SQLAlchemyUnitOfWork()
        customer_repo = SQLAlchemyCustomerRepository(uow.session, task_id=task_id)
        error_repo = SQLAlchemyErrorRepository(uow.session)
        task_repo_uow = SQLAlchemyTaskRepository(uow.session)
        rules = [EmailRule(), UrlRule(), DateRule()]
        process = ProcessChunk(task_repo_uow, customer_repo, error_repo, uow, rules)
        result = process(task_id, rows, 0)

        assert result.valid_count == 1
        assert result.error_count == 2

        session2 = Session()
        task_repo2 = SQLAlchemyTaskRepository(session2)
        customer_repo2 = SQLAlchemyCustomerRepository(session2, task_id=task_id)
        error_repo2 = SQLAlchemyErrorRepository(session2)

        task = task_repo2.get(task_id)
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.processed_rows == 3
        assert customer_repo2.count_by_task(task_id) == 1
        assert len(error_repo2.list_by_task(task_id)) == 2

        session.close()
        session2.close()
