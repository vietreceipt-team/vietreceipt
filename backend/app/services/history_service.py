from uuid import UUID

from backend.app.domain.errors import ReceiptNotFound
from backend.app.domain.models import CorrectionHistory
from backend.app.repositories.protocols import UnitOfWorkFactory


class HistoryService:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def get_correction_history(
        self,
        *,
        receipt_id: UUID,
    ) -> list[CorrectionHistory]:
        async with self._unit_of_work_factory() as unit_of_work:
            receipt = await unit_of_work.receipts.get(
                receipt_id
            )

            if receipt is None:
                raise ReceiptNotFound(
                    f"Receipt {receipt_id} was not found."
                )

            history = list(
                await unit_of_work.correction_history.list_for_receipt(
                    receipt_id
                )
            )

        history.sort(
            key=lambda record: (
                record.changed_at,
                str(record.correction_id),
            )
        )
        return history