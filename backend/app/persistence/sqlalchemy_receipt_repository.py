from collections.abc import Callable
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.errors import PersistenceFailure

from .models import Receipt


class SQLAlchemyReceiptRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def create(self, receipt: Receipt) -> Receipt:
        with self._session_factory() as session:
            try:
                session.add(receipt)
                session.commit()
                session.refresh(receipt)
                return receipt
            except SQLAlchemyError as exc:
                session.rollback()
                raise PersistenceFailure("Could not persist receipt metadata") from exc

    def get_by_id(self, receipt_id: UUID) -> Receipt | None:
        with self._session_factory() as session:
            try:
                return session.get(Receipt, receipt_id)
            except SQLAlchemyError as exc:
                raise PersistenceFailure("Could not read receipt metadata") from exc

    def delete(self, receipt_id: UUID) -> bool:
        with self._session_factory() as session:
            try:
                receipt = session.get(Receipt, receipt_id)
                if receipt is None:
                    return False
                session.delete(receipt)
                session.commit()
                return True
            except SQLAlchemyError as exc:
                session.rollback()
                raise PersistenceFailure("Could not delete receipt metadata") from exc
