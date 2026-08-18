import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from backend.app.domain.enums import (
    CorrectionOperation,
    FieldName,
    ReceiptStatus,
    ValueStatus,
)
from backend.app.domain.errors import ReceiptNotFound
from backend.app.domain.models import (
    CorrectionHistory,
    Receipt,
)
from backend.app.services.history_service import HistoryService
from backend.tests.fakes import FakeUnitOfWork


RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000201")
OCR_RUN_ID = UUID("00000000-0000-4000-8000-000000000202")
KIE_RUN_ID = UUID("00000000-0000-4000-8000-000000000203")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000204")
FIRST_CORRECTION_ID = UUID(
    "00000000-0000-4000-8000-000000000205"
)
SECOND_CORRECTION_ID = UUID(
    "00000000-0000-4000-8000-000000000206"
)

CREATED_AT = datetime(
    2026, 8, 14, 7, 0, tzinfo=timezone.utc
)
FIRST_CHANGED_AT = datetime(
    2026, 8, 14, 7, 5, tzinfo=timezone.utc
)
SECOND_CHANGED_AT = datetime(
    2026, 8, 14, 7, 10, tzinfo=timezone.utc
)


def make_receipt() -> Receipt:
    return Receipt(
        receipt_id=RECEIPT_ID,
        original_filename="receipt.jpg",
        status=ReceiptStatus.NEEDS_REVIEW,
        image_width_px=1000,
        image_height_px=1500,
        latest_ocr_run_id=OCR_RUN_ID,
        latest_kie_run_id=KIE_RUN_ID,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def make_history_record(
    *,
    correction_id: UUID,
    operation: CorrectionOperation,
    old_value: int,
    new_value: int,
    changed_at: datetime,
) -> CorrectionHistory:
    return CorrectionHistory(
        correction_id=correction_id,
        receipt_id=RECEIPT_ID,
        field_name=FieldName.TOTAL_AMOUNT,
        operation=operation,
        kie_run_id=KIE_RUN_ID,
        old_value=old_value,
        new_value=new_value,
        old_status=ValueStatus.PRESENT,
        new_status=ValueStatus.PRESENT,
        changed_by=ACTOR_ID,
        changed_at=changed_at,
    )


def make_service(
    unit_of_work: FakeUnitOfWork,
) -> HistoryService:
    return HistoryService(
        unit_of_work_factory=lambda: unit_of_work,
    )


def test_history_is_returned_oldest_to_newest() -> None:
    receipt = make_receipt()
    first_record = make_history_record(
        correction_id=FIRST_CORRECTION_ID,
        operation=CorrectionOperation.APPLY,
        old_value=325000,
        new_value=330000,
        changed_at=FIRST_CHANGED_AT,
    )
    second_record = make_history_record(
        correction_id=SECOND_CORRECTION_ID,
        operation=CorrectionOperation.CLEAR,
        old_value=330000,
        new_value=325000,
        changed_at=SECOND_CHANGED_AT,
    )

    unit_of_work = FakeUnitOfWork([receipt])
    unit_of_work.correction_history.records.extend(
        [
            second_record,
            first_record,
        ]
    )
    service = make_service(unit_of_work)

    result = asyncio.run(
        service.get_correction_history(
            receipt_id=RECEIPT_ID
        )
    )

    assert result == [
        first_record,
        second_record,
    ]

    assert unit_of_work.correction_history.records == [
        second_record,
        first_record,
    ]
    assert unit_of_work.commit_count == 0


def test_history_returns_empty_list_for_existing_receipt() -> None:
    unit_of_work = FakeUnitOfWork([make_receipt()])
    service = make_service(unit_of_work)

    result = asyncio.run(
        service.get_correction_history(
            receipt_id=RECEIPT_ID
        )
    )

    assert result == []
    assert unit_of_work.commit_count == 0


def test_history_rejects_missing_receipt() -> None:
    unit_of_work = FakeUnitOfWork()
    service = make_service(unit_of_work)

    with pytest.raises(ReceiptNotFound):
        asyncio.run(
            service.get_correction_history(
                receipt_id=RECEIPT_ID
            )
        )

    assert unit_of_work.commit_count == 0