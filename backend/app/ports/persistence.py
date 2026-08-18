from dataclasses import dataclass
from typing import BinaryIO, Protocol, runtime_checkable

from backend.app.domain.models import Receipt


@dataclass(frozen=True, slots=True)
class ReceiptUpload:
    filename: str
    content_type: str | None
    file: BinaryIO


@runtime_checkable
class ReceiptPersistenceService(Protocol):
    async def persist_upload(
        self,
        upload: ReceiptUpload,
    ) -> Receipt:
        """Validate, store and commit a receipt as UPLOADED."""
        ...
