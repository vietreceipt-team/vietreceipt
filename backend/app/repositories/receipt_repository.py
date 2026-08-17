from typing import Protocol, runtime_checkable
from uuid import UUID

from app.persistence.models import Receipt


@runtime_checkable
class ReceiptRepository(Protocol):
    def create(self, receipt: Receipt) -> Receipt: ...
    def get_by_id(self, receipt_id: UUID) -> Receipt | None: ...
    def delete(self, receipt_id: UUID) -> bool: ...
