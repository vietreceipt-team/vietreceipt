import os

from celery import Celery
from sqlalchemy.exc import InterfaceError, OperationalError

from .processing import Processor, dispatch_pending, recover_expired
from .providers import configured_kie, configured_reader
from .runtime import build_service

TASK_NAME = "vietreceipt.v2.process_receipt"
celery_app = Celery(
    "vietreceipt_v2", broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
    task_soft_time_limit=840,
    task_time_limit=870,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "dispatch-invoice-outbox": {"task": "vietreceipt.v2.dispatch", "schedule": 5.0},
        "recover-invoice-leases": {"task": "vietreceipt.v2.recover", "schedule": 60.0},
    },
)


def enqueue_receipt(receipt_id):
    # Exactly one identifier in the message payload; attempts/runs stay in the DB.
    celery_app.send_task(TASK_NAME, args=[receipt_id])


@celery_app.task(
    name=TASK_NAME,
    autoretry_for=(OperationalError, InterfaceError),
    retry_backoff=True,
    max_retries=3,
)
def process_receipt(receipt_id):
    return Processor(build_service(), configured_reader, configured_kie).process(
        receipt_id
    )


@celery_app.task(name="vietreceipt.v2.dispatch")
def dispatch():
    return dispatch_pending(build_service(), enqueue_receipt)


@celery_app.task(name="vietreceipt.v2.recover")
def recover():
    return recover_expired(build_service())
