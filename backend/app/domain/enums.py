from enum import Enum, unique


@unique
class ReceiptStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


@unique
class FieldName(str, Enum):
    MERCHANT_NAME = "merchant_name"
    RECEIPT_DATE = "receipt_date"
    TOTAL_AMOUNT = "total_amount"
    INVOICE_ID = "invoice_id"
    MERCHANT_ADDRESS = "merchant_address"


@unique
class ValueStatus(str, Enum):
    PRESENT = "PRESENT"
    NOT_PRESENT = "NOT_PRESENT"
    UNREADABLE = "UNREADABLE"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


@unique
class CorrectionOperation(str, Enum):
    APPLY = "APPLY"
    CLEAR = "CLEAR"


@unique
class ProcessingStage(str, Enum):
    PREPROCESSING = "PREPROCESSING"
    OCR = "OCR"
    KIE = "KIE"
    PERSISTING = "PERSISTING"


@unique
class ErrorStage(str, Enum):
    SCHEDULING = "SCHEDULING"
    PREPROCESSING = "PREPROCESSING"
    OCR = "OCR"
    KIE = "KIE"
    PERSISTING = "PERSISTING"

@unique
class AuditEventType(str, Enum):
    REVIEW_STARTED = "REVIEW_STARTED"
    CORRECTION_APPLIED = "CORRECTION_APPLIED"
    CORRECTION_CLEARED = "CORRECTION_CLEARED"
    RECEIPT_VERIFIED = "RECEIPT_VERIFIED"
