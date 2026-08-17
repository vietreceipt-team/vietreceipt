from datetime import datetime
from uuid import UUID

from backend.app.domain.enums import (
    AuditEventType,
    CorrectionOperation,
    FieldName,
    ReceiptStatus,
    ValueStatus,
)
from backend.app.domain.errors import (
    FieldNotFound,
    InvalidFieldValue,
    InvalidReceiptState,
    ReceiptNotFound,
    StaleUpdate,
)
from backend.app.domain.models import (
    AuditEvent,
    CorrectionHistory,
    ExtractedField,
)
from backend.app.domain.validation import (
    is_resolved_status,
    validate_canonical_value,
)
from backend.app.ports.clock import Clock
from backend.app.ports.ids import IdGenerator
from backend.app.repositories.protocols import UnitOfWorkFactory


class CorrectionService:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._id_generator = id_generator

    async def update_correction(
        self,
        *,
        receipt_id: UUID,
        field_name: FieldName,
        operation: CorrectionOperation,
        expected_updated_at: datetime,
        actor_id: UUID,
        value: str | int | None = None,
        value_status: ValueStatus | None = None,
    ) -> ExtractedField:
        occurred_at = self._clock.now()

        async with self._unit_of_work_factory() as unit_of_work:
            receipt = await unit_of_work.receipts.get(
                receipt_id
            )

            if receipt is None:
                raise ReceiptNotFound(
                    f"Receipt {receipt_id} was not found."
                )

            if receipt.status is not ReceiptStatus.NEEDS_REVIEW:
                raise InvalidReceiptState(
                    receipt.status,
                    operation="correction",
                )

            field = await unit_of_work.fields.get(
                receipt_id,
                field_name,
            )

            if field is None:
                raise FieldNotFound(
                    f"Field {field_name.value} was not found "
                    f"for receipt {receipt_id}."
                )

            if field.updated_at != expected_updated_at:
                raise StaleUpdate(
                    "Field was updated by another request."
                )

            if operation is CorrectionOperation.APPLY:
                updated_field = self._apply(
                    field=field,
                    value=value,
                    value_status=value_status,
                    occurred_at=occurred_at,
                )
                audit_type = (
                    AuditEventType.CORRECTION_APPLIED
                )
            else:
                updated_field = self._clear(
                    field=field,
                    value=value,
                    value_status=value_status,
                    occurred_at=occurred_at,
                )
                audit_type = (
                    AuditEventType.CORRECTION_CLEARED
                )

            history = CorrectionHistory(
                correction_id=self._id_generator.new_id(),
                receipt_id=receipt_id,
                field_name=field_name,
                operation=operation,
                kie_run_id=field.kie_run_id,
                old_value=field.effective_value,
                new_value=updated_field.effective_value,
                old_status=field.effective_status,
                new_status=updated_field.effective_status,
                changed_by=actor_id,
                changed_at=occurred_at,
            )

            correction_event = AuditEvent(
                event_id=self._id_generator.new_id(),
                receipt_id=receipt_id,
                event_type=audit_type,
                field_name=field_name,
                operation=operation,
                actor_id=actor_id,
                occurred_at=occurred_at,
            )

            receipt_updates: dict[str, object] = {
                "updated_at": occurred_at,
            }

            if receipt.review_started_at is None:
                receipt_updates["review_started_at"] = (
                    occurred_at
                )

                review_event = AuditEvent(
                    event_id=self._id_generator.new_id(),
                    receipt_id=receipt_id,
                    event_type=AuditEventType.REVIEW_STARTED,
                    actor_id=actor_id,
                    occurred_at=occurred_at,
                )
                await unit_of_work.audit_events.append(
                    review_event
                )

            updated_receipt = receipt.model_copy(
                update=receipt_updates
            )

            saved_field = await unit_of_work.fields.save(
                updated_field,
                expected_updated_at=expected_updated_at,
            )
            await unit_of_work.receipts.save(
                updated_receipt,
                expected_updated_at=receipt.updated_at,
            )
            await unit_of_work.correction_history.append(
                history
            )
            await unit_of_work.audit_events.append(
                correction_event
            )
            await unit_of_work.commit()

        return saved_field

    def _apply(
        self,
        *,
        field: ExtractedField,
        value: str | int | None,
        value_status: ValueStatus | None,
        occurred_at: datetime,
    ) -> ExtractedField:
        if value_status is None:
            raise InvalidFieldValue(
                field.field_name,
                "APPLY requires value_status.",
            )

        validate_canonical_value(
            field.field_name,
            value_status,
            value,
        )

        return self._rebuild_field(
            field,
            corrected_value=value,
            corrected_status=value_status,
            has_correction=True,
            effective_value=value,
            effective_status=value_status,
            effective_needs_review=(
                not is_resolved_status(value_status)
            ),
            verified=False,
            updated_at=occurred_at,
        )

    def _clear(
        self,
        *,
        field: ExtractedField,
        value: str | int | None,
        value_status: ValueStatus | None,
        occurred_at: datetime,
    ) -> ExtractedField:
        if value is not None or value_status is not None:
            raise InvalidFieldValue(
                field.field_name,
                "CLEAR cannot contain value or value_status.",
            )

        return self._rebuild_field(
            field,
            corrected_value=None,
            corrected_status=None,
            has_correction=False,
            effective_value=field.normalized_value,
            effective_status=field.value_status,
            effective_needs_review=(
                field.machine_needs_review
                or not is_resolved_status(field.value_status)
            ),
            verified=False,
            updated_at=occurred_at,
        )

    @staticmethod
    def _rebuild_field(
        field: ExtractedField,
        **updates: object,
    ) -> ExtractedField:
        field_data = field.model_dump()
        field_data.update(updates)
        return ExtractedField.model_validate(field_data)
