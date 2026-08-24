from __future__ import annotations

from uuid import UUID

from celery import Celery


PROCESS_RECEIPT_TASK = "vietreceipt.process_receipt"


class CeleryProcessingScheduler:
    def __init__(self, celery_app: Celery) -> None:
        self._celery_app = celery_app

    async def enqueue_receipt(self, receipt_id: UUID) -> None:
        # The durable payload contract is exactly one receipt UUID. Run IDs,
        # attempts, retry policy and state remain database-owned.
        self._celery_app.send_task(
            PROCESS_RECEIPT_TASK,
            args=[str(receipt_id)],
        )
