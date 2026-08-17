from datetime import date
from uuid import UUID

from pydantic import AwareDatetime, Field

from backend.app.api.schemas import APIModel
from backend.app.domain.enums import (
    CorrectionOperation,
    FieldName,
    ProcessingStage,
    ReceiptStatus,
    ValueStatus,
)
from backend.app.domain.models import (
    CorrectionHistory,
    ExtractedField,
    FieldValue,
    NormalizationProvenance,
    ProcessingError,
    Receipt,
)
from backend.app.domain.read_models import (
    OCRBlock,
    ReceiptDetail,
    ReceiptPage,
    ReceiptSummary,
)


class ExtractedFieldResponse(APIModel):
    field_name: FieldName
    ocr_run_id: UUID
    kie_run_id: UUID
    raw_text: str | None
    predicted_value: str | None
    normalized_value: FieldValue
    normalization: NormalizationProvenance | None
    value_status: ValueStatus
    corrected_value: FieldValue
    corrected_status: ValueStatus | None
    has_correction: bool
    effective_value: FieldValue
    effective_status: ValueStatus
    confidence: float = Field(ge=0, le=1)
    machine_needs_review: bool
    effective_needs_review: bool
    review_reasons: tuple[str, ...]
    review_policy_version: str | None
    source_block_ids: tuple[str, ...]
    verified: bool
    updated_at: AwareDatetime

    @classmethod
    def from_domain(
        cls,
        field: ExtractedField,
    ) -> "ExtractedFieldResponse":
        return cls.model_validate(
            field.model_dump(
                exclude={"receipt_id"}
            )
        )


class CanonicalExtractedFieldsResponse(APIModel):
    merchant_name: ExtractedFieldResponse
    receipt_date: ExtractedFieldResponse
    total_amount: ExtractedFieldResponse
    invoice_id: ExtractedFieldResponse
    merchant_address: ExtractedFieldResponse

    @classmethod
    def from_fields(
        cls,
        fields: list[ExtractedField],
    ) -> "CanonicalExtractedFieldsResponse":
        if (
            len(fields) != len(FieldName)
            or {
                field.field_name
                for field in fields
            } != set(FieldName)
        ):
            raise ValueError(
                "Exactly five canonical fields are required."
            )

        responses = {
            field.field_name: (
                ExtractedFieldResponse.from_domain(field)
            )
            for field in fields
        }

        return cls(
            merchant_name=responses[
                FieldName.MERCHANT_NAME
            ],
            receipt_date=responses[
                FieldName.RECEIPT_DATE
            ],
            total_amount=responses[
                FieldName.TOTAL_AMOUNT
            ],
            invoice_id=responses[
                FieldName.INVOICE_ID
            ],
            merchant_address=responses[
                FieldName.MERCHANT_ADDRESS
            ],
        )


class EmptyFieldsResponse(APIModel):
    pass


class ReceiptSummaryResponse(APIModel):
    receipt_id: UUID
    original_filename: str
    status: ReceiptStatus
    merchant_name: str | None = None
    receipt_date: date | None = None
    total_amount: int | None = Field(
        default=None,
        ge=0,
    )
    created_at: AwareDatetime
    verified_at: AwareDatetime | None = None

    @classmethod
    def from_receipt(
        cls,
        receipt: Receipt,
    ) -> "ReceiptSummaryResponse":
        return cls(
            receipt_id=receipt.receipt_id,
            original_filename=receipt.original_filename,
            status=receipt.status,
            created_at=receipt.created_at,
            verified_at=receipt.verified_at,
        )

    @classmethod
    def from_summary(
        cls,
        summary: ReceiptSummary,
    ) -> "ReceiptSummaryResponse":
        return cls.model_validate(
            summary.model_dump()
        )


class ReceiptPageResponse(APIModel):
    items: tuple[ReceiptSummaryResponse, ...]
    page: int
    page_size: int
    total_items: int
    total_pages: int

    @classmethod
    def from_domain(
        cls,
        page: ReceiptPage,
    ) -> "ReceiptPageResponse":
        return cls(
            items=tuple(
                ReceiptSummaryResponse.from_summary(item)
                for item in page.items
            ),
            page=page.page,
            page_size=page.page_size,
            total_items=page.total_items,
            total_pages=page.total_pages,
        )


class ReceiptDetailResponse(APIModel):
    receipt_id: UUID
    original_filename: str
    status: ReceiptStatus
    processing_stage: ProcessingStage | None
    image_url: str | None = None
    image_width_px: int
    image_height_px: int
    latest_ocr_run_id: UUID | None = None
    latest_kie_run_id: UUID | None = None
    fields: (
        CanonicalExtractedFieldsResponse
        | EmptyFieldsResponse
    )
    ocr_blocks: tuple[OCRBlock, ...]
    last_error: ProcessingError | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    processed_at: AwareDatetime | None = None
    verified_at: AwareDatetime | None = None

    @classmethod
    def from_domain(
        cls,
        detail: ReceiptDetail,
    ) -> "ReceiptDetailResponse":
        if detail.fields:
            fields: (
                CanonicalExtractedFieldsResponse
                | EmptyFieldsResponse
            ) = CanonicalExtractedFieldsResponse.from_fields(
                list(detail.fields.values())
            )
        else:
            fields = EmptyFieldsResponse()

        return cls(
            receipt_id=detail.receipt_id,
            original_filename=detail.original_filename,
            status=detail.status,
            processing_stage=detail.processing_stage,
            image_url=detail.image_url,
            image_width_px=detail.image_width_px,
            image_height_px=detail.image_height_px,
            latest_ocr_run_id=detail.latest_ocr_run_id,
            latest_kie_run_id=detail.latest_kie_run_id,
            fields=fields,
            ocr_blocks=detail.ocr_blocks,
            last_error=detail.last_error,
            created_at=detail.created_at,
            updated_at=detail.updated_at,
            processed_at=detail.processed_at,
            verified_at=detail.verified_at,
        )


class CorrectionHistoryResponse(APIModel):
    correction_id: UUID
    receipt_id: UUID
    field_name: FieldName
    operation: CorrectionOperation
    kie_run_id: UUID
    old_value: FieldValue
    new_value: FieldValue
    old_status: ValueStatus | None
    new_status: ValueStatus | None
    changed_by: UUID
    changed_at: AwareDatetime

    @classmethod
    def from_domain(
        cls,
        record: CorrectionHistory,
    ) -> "CorrectionHistoryResponse":
        return cls.model_validate(
            record.model_dump()
        )