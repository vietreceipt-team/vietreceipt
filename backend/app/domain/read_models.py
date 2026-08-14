from datetime import date
from typing import Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    Field,
    model_validator,
)

from backend.app.domain.enums import (
    FieldName,
    ProcessingStage,
    ReceiptStatus,
)
from backend.app.domain.models import (
    DomainModel,
    ExtractedField,
    ProcessingError,
)


class Point(DomainModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class OCRBlock(DomainModel):
    block_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    )
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    polygon: tuple[Point, ...] = Field(
        min_length=4,
        max_length=4,
    )
    reading_order: int = Field(ge=0)


class ReceiptSummary(DomainModel):
    receipt_id: UUID
    original_filename: str = Field(min_length=1)
    status: ReceiptStatus
    merchant_name: str | None = None
    receipt_date: date | None = None
    total_amount: int | None = Field(
        default=None,
        ge=0,
    )
    created_at: AwareDatetime
    verified_at: AwareDatetime | None = None


class ReceiptPage(DomainModel):
    items: tuple[ReceiptSummary, ...]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_total_pages(self) -> Self:
        expected_total_pages = (
            (
                self.total_items
                + self.page_size
                - 1
            )
            // self.page_size
            if self.total_items > 0
            else 0
        )

        if self.total_pages != expected_total_pages:
            raise ValueError(
                "total_pages does not match total_items "
                "and page_size."
            )

        return self


class ReceiptDetail(DomainModel):
    receipt_id: UUID
    original_filename: str = Field(min_length=1)
    status: ReceiptStatus
    processing_stage: ProcessingStage | None = None
    image_url: str | None = None
    image_width_px: int = Field(ge=1)
    image_height_px: int = Field(ge=1)
    latest_ocr_run_id: UUID | None = None
    latest_kie_run_id: UUID | None = None
    fields: dict[FieldName, ExtractedField]
    ocr_blocks: tuple[OCRBlock, ...]
    last_error: ProcessingError | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    processed_at: AwareDatetime | None = None
    verified_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_field_projection(self) -> Self:
        if not self.fields:
            return self

        if set(self.fields) != set(FieldName):
            raise ValueError(
                "Receipt detail fields must be empty or contain "
                "exactly the five canonical fields."
            )

        for field_name, field in self.fields.items():
            if field.field_name is not field_name:
                raise ValueError(
                    "Field dictionary key does not match field_name."
                )

            if field.receipt_id != self.receipt_id:
                raise ValueError(
                    "Projected field belongs to another receipt."
                )

        return self