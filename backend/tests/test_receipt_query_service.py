import asyncio
from datetime import date, datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.app.domain.enums import (
    FieldName,
    ReceiptStatus,
)
from backend.app.domain.errors import (
    PersistenceFailure,
    ReceiptNotFound,
)
from backend.app.domain.read_models import (
    ReceiptDetail,
    ReceiptPage,
    ReceiptSummary,
)
from backend.app.repositories.read_protocols import (
    ReceiptListQuery,
)
from backend.app.services.receipt_query_service import (
    ReceiptQueryService,
)


RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000301")
CREATED_AT = datetime(
    2026, 8, 14, 8, 0, tzinfo=timezone.utc
)


def make_summary() -> ReceiptSummary:
    return ReceiptSummary(
        receipt_id=RECEIPT_ID,
        original_filename="receipt.jpg",
        status=ReceiptStatus.NEEDS_REVIEW,
        merchant_name="VietReceipt Store",
        receipt_date=date(2026, 8, 14),
        total_amount=325000,
        created_at=CREATED_AT,
    )


def make_page() -> ReceiptPage:
    return ReceiptPage(
        items=(make_summary(),),
        page=1,
        page_size=20,
        total_items=1,
        total_pages=1,
    )


def make_detail() -> ReceiptDetail:
    return ReceiptDetail(
        receipt_id=RECEIPT_ID,
        original_filename="receipt.jpg",
        status=ReceiptStatus.UPLOADED,
        image_width_px=1000,
        image_height_px=1500,
        fields={},
        ocr_blocks=(),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


class FakeReceiptReadRepository:
    def __init__(
        self,
        *,
        page: ReceiptPage | None = None,
        detail: ReceiptDetail | None = None,
        error: Exception | None = None,
    ) -> None:
        self.page = page
        self.detail = detail
        self.error = error
        self.queries: list[ReceiptListQuery] = []
        self.requested_receipt_ids: list[UUID] = []

    async def list_page(
        self,
        query: ReceiptListQuery,
    ) -> ReceiptPage:
        self.queries.append(query)

        if self.error is not None:
            raise self.error

        if self.page is None:
            raise AssertionError("Fake page was not configured.")

        return self.page

    async def get_detail(
        self,
        receipt_id: UUID,
    ) -> ReceiptDetail | None:
        self.requested_receipt_ids.append(receipt_id)

        if self.error is not None:
            raise self.error

        return self.detail


def test_list_receipts_delegates_canonical_query() -> None:
    page = make_page()
    repository = FakeReceiptReadRepository(page=page)
    service = ReceiptQueryService(repository=repository)
    query = ReceiptListQuery(
        page=1,
        page_size=20,
        status=ReceiptStatus.NEEDS_REVIEW,
        merchant_name="VietReceipt",
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31),
    )

    result = asyncio.run(
        service.list_receipts(query)
    )

    assert result == page
    assert repository.queries == [query]


def test_get_receipt_returns_detail() -> None:
    detail = make_detail()
    repository = FakeReceiptReadRepository(
        detail=detail
    )
    service = ReceiptQueryService(repository=repository)

    result = asyncio.run(
        service.get_receipt(receipt_id=RECEIPT_ID)
    )

    assert result == detail
    assert repository.requested_receipt_ids == [
        RECEIPT_ID
    ]


def test_get_receipt_rejects_missing_receipt() -> None:
    repository = FakeReceiptReadRepository()
    service = ReceiptQueryService(repository=repository)

    with pytest.raises(ReceiptNotFound):
        asyncio.run(
            service.get_receipt(
                receipt_id=RECEIPT_ID
            )
        )


def test_query_translates_raw_repository_error() -> None:
    repository = FakeReceiptReadRepository(
        error=RuntimeError("database unavailable")
    )
    service = ReceiptQueryService(repository=repository)

    with pytest.raises(PersistenceFailure) as error_info:
        asyncio.run(
            service.list_receipts(
                ReceiptListQuery()
            )
        )

    assert "Receipt list query failed" in str(
        error_info.value
    )


def test_list_query_rejects_reversed_date_range() -> None:
    with pytest.raises(ValidationError):
        ReceiptListQuery(
            date_from=date(2026, 8, 31),
            date_to=date(2026, 8, 1),
        )


def test_receipt_page_rejects_inconsistent_total_pages() -> None:
    with pytest.raises(ValidationError):
        ReceiptPage(
            items=(make_summary(),),
            page=1,
            page_size=20,
            total_items=21,
            total_pages=1,
        )


def test_receipt_detail_rejects_partial_field_projection() -> None:
    detail_data = make_detail().model_dump()
    detail_data["fields"] = {
        FieldName.MERCHANT_NAME: None,
    }

    with pytest.raises(ValidationError):
        ReceiptDetail.model_validate(detail_data)