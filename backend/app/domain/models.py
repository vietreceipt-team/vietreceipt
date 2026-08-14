from typing import Self
from uuid import UUID
from backend.app.domain.validation import validate_canonical_value


from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from backend.app.domain.enums import (
    AuditEventType,
    CorrectionOperation,
    ErrorStage,
    FieldName,
    ProcessingStage,
    ReceiptStatus,
    ValueStatus,
)


FieldValue = str | int | None


class DomainModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class ProcessingError(DomainModel):
    stage: ErrorStage
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool
    occurred_at: AwareDatetime


class NormalizationProvenance(DomainModel):
    rule: str = Field(min_length=1)
    version: str = Field(min_length=1)


class Receipt(DomainModel):
    receipt_id: UUID
    original_filename: str = Field(min_length=1)
    status: ReceiptStatus
    processing_stage: ProcessingStage | None = None
    image_width_px: int = Field(ge=1)
    image_height_px: int = Field(ge=1)
    latest_ocr_run_id: UUID | None = None
    latest_kie_run_id: UUID | None = None
    last_error: ProcessingError | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    review_started_at: AwareDatetime | None = None
    processed_at: AwareDatetime | None = None
    verified_at: AwareDatetime | None = None

class ExtractedField(DomainModel):
    receipt_id: UUID
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

    @model_validator(mode="after")
    def validate_field_invariants(self) -> Self:
        validate_canonical_value(
            self.field_name,
            self.value_status,
            self.normalized_value,
        )

        if self.has_correction:
            if self.corrected_status is None:
                raise ValueError(
                    "Correction requires corrected_status."
                )

            validate_canonical_value(
                self.field_name,
                self.corrected_status,
                self.corrected_value,
            )

            expected_value = self.corrected_value
            expected_status = self.corrected_status
        else:
            if (
                self.corrected_value is not None
                or self.corrected_status is not None
            ):
                raise ValueError(
                    "Field without correction cannot contain "
                    "corrected value or status."
                )

            expected_value = self.normalized_value
            expected_status = self.value_status

        validate_canonical_value(
            self.field_name,
            self.effective_status,
            self.effective_value,
        )

        if (
            self.effective_value != expected_value
            or self.effective_status is not expected_status
        ):
            raise ValueError(
                "Effective value/status must derive from correction "
                "or normalized KIE value/status."
            )

        if len(set(self.source_block_ids)) != len(
            self.source_block_ids
        ):
            raise ValueError(
                "source_block_ids must be unique."
            )

        if self.machine_needs_review:
            if not self.review_reasons:
                raise ValueError(
                    "Machine review requires review reasons."
                )
            if not self.review_policy_version:
                raise ValueError(
                    "Machine review requires policy version."
                )
        elif self.review_reasons:
            raise ValueError(
                "Machine-approved field cannot contain "
                "review reasons."
            )

        return self

class CorrectionHistory(DomainModel):
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


class AuditEvent(DomainModel):
    event_id: UUID
    receipt_id: UUID
    event_type: AuditEventType
    field_name: FieldName | None = None
    operation: CorrectionOperation | None = None
    actor_id: UUID | None = None
    occurred_at: AwareDatetime

    @model_validator(mode="after")
    def validate_event_payload(self) -> Self:
        correction_events = {
            AuditEventType.CORRECTION_APPLIED:
                CorrectionOperation.APPLY,
            AuditEventType.CORRECTION_CLEARED:
                CorrectionOperation.CLEAR,
        }

        expected_operation = correction_events.get(self.event_type)

        if expected_operation is not None:
            if self.field_name is None:
                raise ValueError(
                    "Correction audit event requires field_name."
                )
            if self.operation is not expected_operation:
                raise ValueError(
                    "Correction audit operation does not match event type."
                )
        elif self.field_name is not None or self.operation is not None:
            raise ValueError(
                "Non-correction audit event cannot contain "
                "field_name or operation."
            )

        return self
