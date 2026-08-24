from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.errors import PersistenceFailure, ReceiptNotFound
from backend.app.storage.protocol import ReceiptImageStorage

from .sqlalchemy_receipt_repository import SQLAlchemyReceiptRepository


class SQLAlchemyReceiptImageLoader:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        storage: ReceiptImageStorage,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage

    async def load(self, receipt_id: UUID) -> bytes:
        session = self._session_factory()
        try:
            metadata = await SQLAlchemyReceiptRepository(
                session
            ).get_storage_metadata(receipt_id)
            if metadata is None:
                raise ReceiptNotFound(f"Receipt {receipt_id} was not found.")
            storage_key, _content_type = metadata
            return self._storage.get(storage_key)
        except ReceiptNotFound:
            raise
        except Exception as exc:
            raise PersistenceFailure("Could not load receipt image.") from exc
        finally:
            session.close()
