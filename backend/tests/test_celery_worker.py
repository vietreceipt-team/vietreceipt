from uuid import uuid4

import pytest
from celery.exceptions import Retry

import backend.app.worker.celery_app as worker_module
from backend.app.domain.errors import PersistenceFailure


class FailingOrchestrator:
    def __init__(self) -> None:
        self.delivery_ids: list[str] = []

    async def process(self, receipt_id, *, delivery_id):
        self.delivery_ids.append(delivery_id)
        raise PersistenceFailure("simulated database outage")


def test_task_retries_transient_persistence_failure(monkeypatch):
    orchestrator = FailingOrchestrator()

    monkeypatch.setattr(
        worker_module,
        "_get_orchestrator",
        lambda: orchestrator,
    )

    worker_module.process_receipt.push_request(
        id="db-retry-delivery",
        retries=0,
        called_directly=False,
        is_eager=True,
    )
    try:
        with pytest.raises(Retry) as exc_info:
            worker_module.process_receipt.run(str(uuid4()))
    finally:
        worker_module.process_receipt.pop_request()

    assert orchestrator.delivery_ids == ["db-retry-delivery"]
    assert isinstance(exc_info.value.exc, RuntimeError)
    assert (
        str(exc_info.value.exc)
        == "transient processing persistence failure"
    )


def test_task_redelivers_after_worker_loss():
    assert worker_module.process_receipt.acks_late is True
    assert worker_module.process_receipt.reject_on_worker_lost is True
    assert worker_module.process_receipt.max_retries == 3
