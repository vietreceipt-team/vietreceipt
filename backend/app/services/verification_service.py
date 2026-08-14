from datetime import datetime
from uuid import UUID

from backend.app.domain.enums import (
    AuditEventType,
    FieldName,
    ReceiptStatus,
)
from backend.app.domain.errors import (
    InvalidReceiptState,
    ReceiptNotFound,
    StaleUpdate,
    VerificationFailure,
)
from backend.app.domain.models import (
    AuditEvent,
    ExtractedField,
    Receipt,
)
from backend.app.domain.validation import (
    is_resolved_status,
    validate_canonical_value,
)
from backend.app.ports.clock import Clock
from backend.app.ports.ids import IdGenerator
from backend.app.repositories.protocols import UnitOfWorkFactory


CANONICAL_FIELD_NAMES = frozenset(FieldName)

FIELD_ORDER = {
    field_name: position
    for position, field_name in enumerate(FieldName)
}


class VerificationService:
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

    async def get_fields(
        self,
        *,
        receipt_id: UUID,
        actor_id: UUID | None = None,
    ) -> list[ExtractedField]:
        async with self._unit_of_work_factory() as unit_of_work:
            receipt = await unit_of_work.receipts.get(
                receipt_id
            )

            if receipt is None:
                raise ReceiptNotFound(
                    f"Receipt {receipt_id} was not found."
                )

            if receipt.status not in {
                ReceiptStatus.NEEDS_REVIEW,
                ReceiptStatus.VERIFIED,
            }:
                raise InvalidReceiptState(
                    receipt.status,
                    operation="get_fields",
                )

            if receipt.latest_kie_run_id is None:
                raise VerificationFailure(
                    "Receipt has no canonical KIE result."
                )

            fields = list(
                await unit_of_work.fields.list_for_receipt(
                    receipt_id,
                    kie_run_id=receipt.latest_kie_run_id,
                )
            )
            fields.sort(
                key=lambda field: FIELD_ORDER[field.field_name]
            )

            if (
                receipt.status is ReceiptStatus.NEEDS_REVIEW
                and receipt.review_started_at is None
            ):
                occurred_at = self._clock.now()

                updated_receipt = receipt.model_copy(
                    update={
                        "review_started_at": occurred_at,
                    }
                )

                review_event = AuditEvent(
                    event_id=self._id_generator.new_id(),
                    receipt_id=receipt_id,
                    event_type=AuditEventType.REVIEW_STARTED,
                    actor_id=actor_id,
                    occurred_at=occurred_at,
                )

                await unit_of_work.receipts.save(
                    updated_receipt,
                    expected_updated_at=receipt.updated_at,
                )
                await unit_of_work.audit_events.append(
                    review_event
                )
                await unit_of_work.commit()

        return fields

    async def verify_receipt(
        self,
        *,
        receipt_id: UUID,
        expected_updated_at: datetime,
        actor_id: UUID | None = None,
    ) -> Receipt:
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
                    operation="verify",
                )

            if receipt.updated_at != expected_updated_at:
                raise StaleUpdate(
                    "Receipt was updated by another request."
                )

            if receipt.latest_kie_run_id is None:
                raise VerificationFailure(
                    "Receipt has no canonical KIE result."
                )

            fields = list(
                await unit_of_work.fields.list_for_receipt(
                    receipt_id,
                    kie_run_id=receipt.latest_kie_run_id,
                )
            )

            self._validate_verifiable_fields(fields)

            updated_fields = [
                self._rebuild_verified_field(
                    field,
                    occurred_at=occurred_at,
                )
                for field in fields
            ]

            review_started_at = receipt.review_started_at
            audit_events: list[AuditEvent] = []

            if review_started_at is None:
                review_started_at = occurred_at
                audit_events.append(
                    AuditEvent(
                        event_id=self._id_generator.new_id(),
                        receipt_id=receipt_id,
                        event_type=(
                            AuditEventType.REVIEW_STARTED
                        ),
                        actor_id=actor_id,
                        occurred_at=occurred_at,
                    )
                )

            audit_events.append(
                AuditEvent(
                    event_id=self._id_generator.new_id(),
                    receipt_id=receipt_id,
                    event_type=AuditEventType.RECEIPT_VERIFIED,
                    actor_id=actor_id,
                    occurred_at=occurred_at,
                )
            )

            updated_receipt = receipt.model_copy(
                update={
                    "status": ReceiptStatus.VERIFIED,
                    "updated_at": occurred_at,
                    "review_started_at": review_started_at,
                    "verified_at": occurred_at,
                }
            )

            for old_field, updated_field in zip(
                fields,
                updated_fields,
                strict=True,
            ):
                await unit_of_work.fields.save(
                    updated_field,
                    expected_updated_at=old_field.updated_at,
                )

            saved_receipt = await unit_of_work.receipts.save(
                updated_receipt,
                expected_updated_at=expected_updated_at,
            )

            for audit_event in audit_events:
                await unit_of_work.audit_events.append(
                    audit_event
                )

            await unit_of_work.commit()

        return saved_receipt

    @staticmethod
    def _validate_verifiable_fields(
        fields: list[ExtractedField],
    ) -> None:
        field_names = {
            field.field_name
            for field in fields
        }

        if (
            len(fields) != len(CANONICAL_FIELD_NAMES)
            or field_names != CANONICAL_FIELD_NAMES
        ):
            raise VerificationFailure(
                "Verification requires exactly the five "
                "canonical fields."
            )

        for field in fields:
            if (
                not is_resolved_status(field.effective_status)
                or field.effective_needs_review
            ):
                raise VerificationFailure(
                    f"Field {field.field_name.value} "
                    f"still requires review."
                )

            validate_canonical_value(
                field.field_name,
                field.effective_status,
                field.effective_value,
            )

    @staticmethod
    def _rebuild_verified_field(
        field: ExtractedField,
        *,
        occurred_at: datetime,
    ) -> ExtractedField:
        field_data = field.model_dump()
        field_data.update(
            {
                "verified": True,
                "effective_needs_review": False,
                "updated_at": occurred_at,
            }
        )
        return ExtractedField.model_validate(field_data)