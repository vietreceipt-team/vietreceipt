from backend.app.domain.enums import FieldName, ReceiptStatus


class DomainError(Exception):
    code = "DOMAIN_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ReceiptNotFound(DomainError):
    code = "RECEIPT_NOT_FOUND"


class InvalidReceiptState(DomainError):
    code = "RECEIPT_STATE_CONFLICT"

    def __init__(
        self,
        current_status: ReceiptStatus,
        target_status: ReceiptStatus,
    ) -> None:
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Receipt cannot transition from "
            f"{current_status.value} to {target_status.value}."
        )


class StaleUpdate(DomainError):
    code = "STALE_UPDATE"


class InvalidFieldValue(DomainError):
    code = "INVALID_FIELD_VALUE"

    def __init__(self, field_name: FieldName, reason: str) -> None:
        self.field_name = field_name
        self.reason = reason
        super().__init__(f"Invalid value for {field_name.value}: {reason}")


class SchedulingFailure(DomainError):
    code = "SCHEDULING_FAILED"


class PersistenceFailure(DomainError):
    code = "PERSISTENCE_FAILED"