from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from backend.app.domain.enums import ErrorStage
from backend.app.domain.models import ProcessingError
from backend.app.ports.clock import Clock
from backend.app.repositories.protocols import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class ProcessingRecoveryService:
    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    stale_after: timedelta

    def __post_init__(self) -> None:
        if self.stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive.")

    async def recover_stale_attempts(self) -> int:
        now = self.clock.now()
        error = ProcessingError(
            stage=ErrorStage.PERSISTING,
            code="PROCESSING_ATTEMPT_EXPIRED",
            message="Processing attempt expired before completion.",
            retryable=True,
            occurred_at=now,
        )

        async with self.unit_of_work_factory() as uow:
            recovered = await uow.processing.reap_stale_attempts(
                stale_before=now - self.stale_after,
                failed_at=now,
                error=error,
            )
            if recovered:
                await uow.commit()
            return recovered
