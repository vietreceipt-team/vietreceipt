from typing import Self
from uuid import UUID

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
