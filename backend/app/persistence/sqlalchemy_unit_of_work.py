from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.errors import PersistenceFailure

from .sqlalchemy_receipt_repository import SQLAlchemyReceiptRepository
from .sqlalchemy_processing_repository import SQLAlchemyProcessingRepository


class SQLAlchemyUnitOfWork:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self.receipts: SQLAlchemyReceiptRepository
        self.processing: SQLAlchemyProcessingRepository

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.receipts = SQLAlchemyReceiptRepository(self._session)
        self.processing = SQLAlchemyProcessingRepository(self._session)
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
    def __init__(
        self,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(self._session_factory)
