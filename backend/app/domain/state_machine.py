from typing import Final

from backend.app.domain.enums import ReceiptStatus
from backend.app.domain.errors import InvalidReceiptState


VALID_TRANSITIONS: Final[frozenset[tuple[ReceiptStatus, ReceiptStatus]]] = (
    frozenset(
        {
            (ReceiptStatus.UPLOADED, ReceiptStatus.PROCESSING),
            (ReceiptStatus.UPLOADED, ReceiptStatus.FAILED),
            (ReceiptStatus.PROCESSING, ReceiptStatus.NEEDS_REVIEW),
            (ReceiptStatus.PROCESSING, ReceiptStatus.FAILED),
            (ReceiptStatus.FAILED, ReceiptStatus.PROCESSING),
            (ReceiptStatus.NEEDS_REVIEW, ReceiptStatus.VERIFIED),
        }
    )
)


def can_transition(
    current_status: ReceiptStatus,
    target_status: ReceiptStatus,
) -> bool:
    return (current_status, target_status) in VALID_TRANSITIONS


def ensure_transition_allowed(
    current_status: ReceiptStatus,
    target_status: ReceiptStatus,
) -> None:
    if not can_transition(current_status, target_status):
        raise InvalidReceiptState(current_status, target_status)