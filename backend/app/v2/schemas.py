from typing import Literal

from pydantic import BaseModel, ConfigDict

from .contracts import HEADER_FIELDS


class FieldView(BaseModel):
    model_config = ConfigDict(extra="allow")
    raw_text: str | None
    normalized_value: str | int | float | None
    value_status: Literal[
        "PRESENT", "NOT_PRESENT", "UNREADABLE", "AMBIGUOUS", "UNKNOWN"
    ]
    source_block_ids: list[str]
    corrected_value: str | int | float | None
    corrected_status: str | None
    has_correction: bool
    effective_value: str | int | float | None
    effective_status: str
    reviewed: bool
    effective_needs_review: bool
    confidence: float | None = None
    machine_needs_review: bool = True
    review_reasons: list[str] = []


class LineView(BaseModel):
    line_id: str
    description: FieldView
    unit: FieldView
    quantity: FieldView
    unit_price: FieldView
    amount: FieldView


class TaxView(BaseModel):
    tax_id: str
    rate: FieldView
    taxable_amount: FieldView
    tax_amount: FieldView


class ProcessingErrorView(BaseModel):
    stage: str
    code: str
    message: str
    retryable: bool


class Summary(BaseModel):
    receipt_id: str
    original_filename: str
    status: Literal["UPLOADED", "PROCESSING", "NEEDS_REVIEW", "VERIFIED", "FAILED"]
    version: int
    created_at: str
    seller_name: str | None = None
    invoice_date: str | None = None
    total_amount: int | None = None


class InvoiceDetail(BaseModel):
    receipt_id: str
    original_filename: str
    content_type: str
    source_group: Literal["PAPER_DIGITIZED", "IMAGE", "PDF"]
    status: Literal["UPLOADED", "PROCESSING", "NEEDS_REVIEW", "VERIFIED", "FAILED"]
    version: int
    created_at: str
    updated_at: str
    verified_at: str | None
    source_url: str
    evidence_url: str
    latest_ocr_run_id: str | None
    latest_kie_run_id: str | None
    processing_stage: str | None
    processing_error: ProcessingErrorView | None
    fields: dict[Literal[tuple(HEADER_FIELDS)], FieldView]
    line_items: list[LineView]
    tax_breakdown: list[TaxView]


class InvoicePage(BaseModel):
    items: list[Summary]
    limit: int
    offset: int


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody
