from dataclasses import dataclass
from uuid import UUID

from fastapi import Request

from backend.app.services.correction_service import (
    CorrectionService,
)
from backend.app.services.history_service import HistoryService
from backend.app.services.receipt_query_service import (
    ReceiptQueryService,
)
from backend.app.services.receipt_service import ReceiptService
from backend.app.services.verification_service import (
    VerificationService,
)


SYSTEM_ACTOR_ID = UUID(
    "00000000-0000-0000-0000-000000000000"
)


class ApplicationServicesUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ServiceRegistry:
    receipts: ReceiptService
    receipt_queries: ReceiptQueryService
    corrections: CorrectionService
    verification: VerificationService
    history: HistoryService


def get_service_registry(
    request: Request,
) -> ServiceRegistry:
    registry = getattr(
        request.app.state,
        "service_registry",
        None,
    )

    if registry is None:
        raise ApplicationServicesUnavailable(
            "Application service adapters are not configured."
        )

    return registry


def get_receipt_service(
    request: Request,
) -> ReceiptService:
    return get_service_registry(request).receipts


def get_receipt_query_service(
    request: Request,
) -> ReceiptQueryService:
    return get_service_registry(request).receipt_queries


def get_correction_service(
    request: Request,
) -> CorrectionService:
    return get_service_registry(request).corrections


def get_verification_service(
    request: Request,
) -> VerificationService:
    return get_service_registry(request).verification


def get_history_service(
    request: Request,
) -> HistoryService:
    return get_service_registry(request).history


def get_actor_id() -> UUID:
    return SYSTEM_ACTOR_ID