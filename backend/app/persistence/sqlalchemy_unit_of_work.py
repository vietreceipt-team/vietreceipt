from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.errors import PersistenceFailure

from .sqlalchemy_receipt_repository import SQLAlchemyReceiptRepository


class SQLAlchemyUnitOfWork:
    """Receipt-only SQLAlchemy persistence helper, not the canonical UnitOfWork.

    The canonical backend ``UnitOfWork`` also requires ``fields``,
    ``correction_history``, and ``audit_events``. Those adapters are outside this
    receipt-persistence slice, so this helper deliberately exposes only
    ``receipts`` and must not be wired where the full canonical UnitOfWork is
    required.
    """

    def __init__(
        self,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self.receipts: SQLAlchemyReceiptRepository

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.receipts = SQLAlchemyReceiptRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None:
                self._session.rollback()
        finally:
            self._session.close()
            self._session = None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of work has not been entered.")
        try:
            self._session.commit()
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise PersistenceFailure(
                "Database commit failed."
            ) from exc

    async def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()


class SQLAlchemyUnitOfWorkFactory:
    """Factory for the receipt-only persistence helper above."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(self._session_factory)
