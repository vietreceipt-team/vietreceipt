from datetime import date
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field, model_validator
from typing_extensions import Self

from backend.app.domain.enums import ReceiptStatus
from backend.app.domain.models import DomainModel
from backend.app.domain.read_models import (
    ReceiptDetail,
    ReceiptPage,
)


class ReceiptListQuery(DomainModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: ReceiptStatus | None = None
    merchant_name: str | None = Field(
        default=None,
        min_length=1,
    )
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError(
                "date_from cannot be later than date_to."
            )

        return self


@runtime_checkable
class ReceiptReadRepository(Protocol):
    async def list_page(
        self,
        query: ReceiptListQuery,
    ) -> ReceiptPage:
        ...

    async def get_detail(
        self,
        receipt_id: UUID,
    ) -> ReceiptDetail | None:
        ...