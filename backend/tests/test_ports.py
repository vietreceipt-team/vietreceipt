import asyncio
from datetime import datetime, timezone
from uuid import UUID

from backend.app.ports.clock import Clock, SystemClock
from backend.app.ports.scheduler import ProcessingScheduler


RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000001")
FIXED_NOW = datetime(2026, 8, 14, 4, 0, tzinfo=timezone.utc)


class FixedClock:
    def now(self) -> datetime:
        return FIXED_NOW


class FakeProcessingScheduler:
    def __init__(self) -> None:
        self.enqueued_receipt_ids: list[UUID] = []

    async def enqueue_receipt(self, receipt_id: UUID) -> None:
        self.enqueued_receipt_ids.append(receipt_id)


def test_system_clock_returns_timezone_aware_utc_time() -> None:
    current = SystemClock().now()

    assert current.tzinfo is not None
    assert current.utcoffset() == timezone.utc.utcoffset(current)


def test_fixed_clock_satisfies_clock_port() -> None:
    clock = FixedClock()

    assert isinstance(clock, Clock)
    assert clock.now() == FIXED_NOW


def test_fake_scheduler_satisfies_scheduler_port() -> None:
    scheduler = FakeProcessingScheduler()

    assert isinstance(scheduler, ProcessingScheduler)

    asyncio.run(scheduler.enqueue_receipt(RECEIPT_ID))

    assert scheduler.enqueued_receipt_ids == [RECEIPT_ID]
