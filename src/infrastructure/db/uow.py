"""Implementación de Unit of Work con SQLAlchemy.

El UoW actúa como context manager: al entrar expone la sesión,
al salir hace rollback si hubo excepción, y commit() persiste
explícitamente.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from infrastructure.db.connection import SessionLocal


class SQLAlchemyUnitOfWork:
    """Unidad de trabajo sobre una sesión SQLAlchemy.

    Uso típico::

        uow = SQLAlchemyUnitOfWork()
        repo = MiRepo(uow.session)
        with uow:
            repo.do_work()
            uow.commit()
    """

    def __init__(self, session_factory: Any = SessionLocal) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    @property
    def session(self) -> Session:
        """Retorna la sesión activa, creándola si es necesario."""
        if self._session is None:
            self._session = self._session_factory()
        return self._session

    def __enter__(self) -> SQLAlchemyUnitOfWork:
        """Inicia el contexto de trabajo."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Rollback automático si salió por excepción; luego cierra sesión."""
        try:
            if exc_type is not None and self._session is not None:
                self._session.rollback()
        finally:
            if self._session is not None:
                self._session.close()
                self._session = None

    def commit(self) -> None:
        """Confirma la transacción actual."""
        self.session.commit()

    def rollback(self) -> None:
        """Revierte la transacción actual."""
        if self._session is not None:
            self._session.rollback()
