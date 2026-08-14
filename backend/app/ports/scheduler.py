from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class ProcessingScheduler(Protocol):
    async def enqueue_receipt(self, receipt_id: UUID) -> None:
        """Request asynchronous processing for a committed receipt."""
        ...
