import re
from datetime import date

from backend.app.domain.enums import FieldName, ValueStatus
from backend.app.domain.errors import InvalidFieldValue


ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

STRING_FIELDS = {
    FieldName.MERCHANT_NAME,
    FieldName.INVOICE_ID,
    FieldName.MERCHANT_ADDRESS,
}

UNRESOLVED_STATUSES = {
    ValueStatus.AMBIGUOUS,
    ValueStatus.UNKNOWN,
}


def validate_canonical_value(
    field_name: FieldName,
    value_status: ValueStatus,
    value: str | int | None,
) -> None:
    if value_status is not ValueStatus.PRESENT:
        if value is not None:
            raise InvalidFieldValue(
                field_name,
                "Non-PRESENT status requires a null value.",
            )
        return

    if field_name in STRING_FIELDS:
        if type(value) is not str or not value.strip():
            raise InvalidFieldValue(
                field_name,
                "PRESENT value must be a non-empty string.",
            )
        return

    if field_name is FieldName.TOTAL_AMOUNT:
        if type(value) is not int or value < 0:
            raise InvalidFieldValue(
                field_name,
                "PRESENT value must be a non-negative integer.",
            )
        return

    if field_name is FieldName.RECEIPT_DATE:
        if (
            type(value) is not str
            or ISO_DATE_PATTERN.fullmatch(value) is None
        ):
            raise InvalidFieldValue(
                field_name,
                "PRESENT value must use ISO YYYY-MM-DD.",
            )

        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise InvalidFieldValue(
                field_name,
                "PRESENT value must be a valid calendar date.",
            ) from error

        return

    raise InvalidFieldValue(
        field_name,
        "Unsupported canonical field.",
    )


def is_resolved_status(value_status: ValueStatus) -> bool:
    return value_status not in UNRESOLVED_STATUSES
