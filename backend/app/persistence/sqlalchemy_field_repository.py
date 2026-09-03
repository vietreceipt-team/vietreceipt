from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.domain.enums import FieldName, ValueStatus
from backend.app.domain.errors import PersistenceFailure, StaleUpdate
from backend.app.domain.models import (
    ExtractedField,
    NormalizationProvenance,
)

from .models import ExtractedFieldRecord


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_domain(record: ExtractedFieldRecord) -> ExtractedField:
    return ExtractedField(
        receipt_id=record.receipt_id,
        field_name=FieldName(record.field_name),
        ocr_run_id=record.ocr_run_id,
        kie_run_id=record.kie_run_id,
        raw_text=record.raw_text,
        predicted_value=record.predicted_value,
        normalized_value=record.normalized_value,
        normalization=(
            NormalizationProvenance.model_validate(
                record.normalization
            )
            if record.normalization is not None
            else None
        ),
        value_status=ValueStatus(record.value_status),
        corrected_value=record.corrected_value,
        corrected_status=(
            ValueStatus(record.corrected_status)
            if record.corrected_status is not None
            else None
        ),
        has_correction=record.has_correction,
        effective_value=record.effective_value,
        effective_status=ValueStatus(record.effective_status),
        confidence=record.confidence,
        machine_needs_review=record.machine_needs_review,
        effective_needs_review=record.effective_needs_review,
        review_reasons=tuple(record.review_reasons),
        review_policy_version=record.review_policy_version,
        source_block_ids=tuple(record.source_block_ids),
        verified=record.verified,
        updated_at=_aware(record.updated_at),
    )


def _record_values(field: ExtractedField) -> dict[str, object]:
    return {
        "ocr_run_id": field.ocr_run_id,
        "kie_run_id": field.kie_run_id,
        "raw_text": field.raw_text,
        "predicted_value": field.predicted_value,
        "normalized_value": field.normalized_value,
        "normalization": (
            field.normalization.model_dump(mode="json")
            if field.normalization is not None
            else None
        ),
        "value_status": field.value_status.value,
        "corrected_value": field.corrected_value,
        "corrected_status": (
            field.corrected_status.value
            if field.corrected_status is not None
            else None
        ),
        "has_correction": field.has_correction,
        "effective_value": field.effective_value,
        "effective_status": field.effective_status.value,
        "confidence": field.confidence,
        "machine_needs_review": field.machine_needs_review,
        "effective_needs_review": field.effective_needs_review,
        "review_reasons": list(field.review_reasons),
        "review_policy_version": field.review_policy_version,
        "source_block_ids": list(field.source_block_ids),
        "verified": field.verified,
        "updated_at": field.updated_at,
    }


class SQLAlchemyFieldRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_initial(self, field: ExtractedField) -> None:
        record = ExtractedFieldRecord(
            receipt_id=field.receipt_id,
            field_name=field.field_name.value,
            **_record_values(field),
        )
        try:
            self._session.add(record)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not persist initial extracted field."
            ) from exc

    async def get(
        self,
        receipt_id: UUID,
        field_name: FieldName,
    ) -> ExtractedField | None:
        try:
            record = self._session.get(
                ExtractedFieldRecord,
                (receipt_id, field_name.value),
            )
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not read extracted field."
            ) from exc

        return (
            _to_domain(record)
            if record is not None
            else None
        )

    async def list_for_receipt(
        self,
        receipt_id: UUID,
        *,
        kie_run_id: UUID | None = None,
    ) -> list[ExtractedField]:
        statement = (
            select(ExtractedFieldRecord)
            .where(
                ExtractedFieldRecord.receipt_id == receipt_id
            )
            .order_by(ExtractedFieldRecord.field_name)
        )

        if kie_run_id is not None:
            statement = statement.where(
                ExtractedFieldRecord.kie_run_id == kie_run_id
            )

        try:
            records = self._session.scalars(statement).all()
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not list extracted fields."
            ) from exc

        return [_to_domain(record) for record in records]

    async def save(
        self,
        field: ExtractedField,
        *,
        expected_updated_at: datetime,
    ) -> ExtractedField:
        statement = (
            update(ExtractedFieldRecord)
            .where(
                ExtractedFieldRecord.receipt_id
                == field.receipt_id,
                ExtractedFieldRecord.field_name
                == field.field_name.value,
                ExtractedFieldRecord.updated_at
                == expected_updated_at,
            )
            .values(**_record_values(field))
            .execution_options(synchronize_session=False)
        )

        try:
            result = self._session.execute(statement)

            if result.rowcount != 1:
                raise StaleUpdate(
                    "Field was updated by another request."
                )

            self._session.flush()
            return field

        except StaleUpdate:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not update extracted field."
            ) from exc
