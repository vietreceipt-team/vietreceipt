import os

from celery import Celery

# No tasks are registered here: task/receipt-processing logic belongs to
# Backend-1/Backend-2. This app only proves the worker can reach Redis.
celery_app = Celery(
    "vietreceipt_worker",
    broker=os.environ.get(
        "CELERY_BROKER_URL", "redis://redis:6379/0"
    ),
    backend=os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://redis:6379/1"
    ),
)
