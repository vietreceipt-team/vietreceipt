from __future__ import annotations

import asyncio
import os
from uuid import UUID

from celery import Celery

from backend.app.adapters.celery_scheduler import PROCESS_RECEIPT_TASK
from backend.app.bootstrap import build_processing_orchestrator
from backend.app.domain.errors import PersistenceFailure
from backend.app.services.processing_orchestrator import ProcessingOutcome


celery_app = Celery(
    "vietreceipt_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = build_processing_orchestrator()
    return _orchestrator


@celery_app.task(
    bind=True,
    name=PROCESS_RECEIPT_TASK,
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_receipt(self, receipt_id: str) -> dict[str, str | bool | None]:
    receipt_uuid = UUID(receipt_id)
    delivery_id = str(self.request.id)
    countdown = min(60, 2 ** (self.request.retries + 1))

    try:
        result = asyncio.run(
            _get_orchestrator().process(
                receipt_uuid,
                delivery_id=delivery_id,
            )
        )
    except PersistenceFailure:
        raise self.retry(
            exc=RuntimeError(
                "transient processing persistence failure"
            ),
            countdown=countdown,
        ) from None

    if result.outcome is ProcessingOutcome.FAILED and result.retryable:
        raise self.retry(
            exc=RuntimeError("retryable receipt processing failure"),
            countdown=countdown,
        )
    return {
        "outcome": result.outcome.value,
        "receipt_id": str(result.receipt_id),
        "attempt_id": str(result.attempt_id) if result.attempt_id else None,
        "retryable": result.retryable,
    }
