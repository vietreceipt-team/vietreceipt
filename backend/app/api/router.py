from datetime import date
from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from backend.app.api.dependencies import (
    get_actor_id,
    get_correction_service,
    get_history_service,
    get_receipt_query_service,
    get_receipt_service,
    get_verification_service,
)
from backend.app.api.responses import (
    CanonicalExtractedFieldsResponse,
    CorrectionHistoryResponse,
    ExtractedFieldResponse,
    ReceiptDetailResponse,
    ReceiptPageResponse,
    ReceiptSummaryResponse,
)
from backend.app.api.schemas import (
    ApplyFieldCorrectionRequest,
    ErrorResponse,
    FieldCorrectionRequest,
    RetryAcceptedResponse,
    VerifyReceiptRequest,
)
from backend.app.domain.enums import (
    CorrectionOperation,
    FieldName,
    ReceiptStatus,
)
from backend.app.ports.persistence import ReceiptUpload
from backend.app.repositories.read_protocols import (
    ReceiptListQuery,
)
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


API_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_PREFIX)


ReceiptServiceDependency: TypeAlias = Annotated[
    ReceiptService,
    Depends(get_receipt_service),
]

ReceiptQueryServiceDependency: TypeAlias = Annotated[
    ReceiptQueryService,
    Depends(get_receipt_query_service),
]

CorrectionServiceDependency: TypeAlias = Annotated[
    CorrectionService,
    Depends(get_correction_service),
]

VerificationServiceDependency: TypeAlias = Annotated[
    VerificationService,
    Depends(get_verification_service),
]

HistoryServiceDependency: TypeAlias = Annotated[
    HistoryService,
    Depends(get_history_service),
]

ActorIdDependency: TypeAlias = Annotated[
    UUID,
    Depends(get_actor_id),
]
NOT_FOUND_RESPONSE = {
    404: {
        "model": ErrorResponse,
        "description": "Receipt or field not found.",
    }
}
CONFLICT_RESPONSE = {
    409: {
        "model": ErrorResponse,
        "description": "State or concurrency conflict.",
    }
}
VALIDATION_RESPONSE = {
    422: {
        "model": ErrorResponse,
        "description": "Request or field validation failed.",
    }
}


@api_router.post(
    "/receipts",
    operation_id="uploadReceipt",
    status_code=201,
    response_model=ReceiptSummaryResponse,
)
async def upload_receipt(
    service: ReceiptServiceDependency,
    file: Annotated[UploadFile, File()],
) -> ReceiptSummaryResponse:
    receipt = await service.upload_receipt(
        ReceiptUpload(
            filename=file.filename or "receipt",
            content_type=file.content_type,
            file=file.file,
        )
    )
    return ReceiptSummaryResponse.from_receipt(receipt)


@api_router.get(
    "/receipts",
    operation_id="listReceipts",
    response_model=ReceiptPageResponse,
)
async def list_receipts(
    service: ReceiptQueryServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 20,
    status: Annotated[
        ReceiptStatus | None,
        Query(),
    ] = None,
    merchant_name: Annotated[
        str | None,
        Query(min_length=1),
    ] = None,
    date_from: Annotated[
        date | None,
        Query(),
    ] = None,
    date_to: Annotated[
        date | None,
        Query(),
    ] = None,
) -> ReceiptPageResponse:
    try:
        query = ReceiptListQuery(
            page=page,
            page_size=page_size,
            status=status,
            merchant_name=merchant_name,
            date_from=date_from,
            date_to=date_to,
        )
    except ValidationError as error:
        raise RequestValidationError(
            error.errors()
        ) from error

    result = await service.list_receipts(query)
    return ReceiptPageResponse.from_domain(result)


@api_router.get(
    "/receipts/{receipt_id}",
    operation_id="getReceipt",
    response_model=ReceiptDetailResponse,
    responses=NOT_FOUND_RESPONSE,
)
async def get_receipt(
    receipt_id: UUID,
    service: ReceiptQueryServiceDependency,
) -> ReceiptDetailResponse:
    detail = await service.get_receipt(
        receipt_id=receipt_id
    )
    return ReceiptDetailResponse.from_domain(detail)


@api_router.post(
    "/receipts/{receipt_id}/retry",
    operation_id="retryReceipt",
    status_code=202,
    response_model=RetryAcceptedResponse,
    responses={
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
    },
)
async def retry_receipt(
    receipt_id: UUID,
    service: ReceiptServiceDependency,
) -> RetryAcceptedResponse:
    accepted_receipt_id = await service.retry_receipt(
        receipt_id
    )
    return RetryAcceptedResponse(
        receipt_id=accepted_receipt_id
    )


@api_router.get(
    "/receipts/{receipt_id}/fields",
    operation_id="getReceiptFields",
    response_model=CanonicalExtractedFieldsResponse,
    responses={
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
    },
)
async def get_receipt_fields(
    receipt_id: UUID,
    service: VerificationServiceDependency,
    actor_id: ActorIdDependency,
    kie_run_id: Annotated[
        UUID | None,
        Query(),
    ] = None,
) -> CanonicalExtractedFieldsResponse:
    fields = await service.get_fields(
        receipt_id=receipt_id,
        kie_run_id=kie_run_id,
        actor_id=actor_id,
    )
    return CanonicalExtractedFieldsResponse.from_fields(
        fields
    )


@api_router.patch(
    "/receipts/{receipt_id}/fields/"
    "{field_name}/correction",
    operation_id="updateFieldCorrection",
    response_model=ExtractedFieldResponse,
    responses={
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
        **VALIDATION_RESPONSE,
    },
)
async def update_field_correction(
    receipt_id: UUID,
    field_name: FieldName,
    payload: FieldCorrectionRequest,
    service: CorrectionServiceDependency,
    actor_id: ActorIdDependency,
) -> ExtractedFieldResponse:
    operation = CorrectionOperation(
        payload.operation
    )

    if isinstance(
        payload,
        ApplyFieldCorrectionRequest,
    ):
        value = payload.value
        value_status = payload.value_status
    else:
        value = None
        value_status = None

    field = await service.update_correction(
        receipt_id=receipt_id,
        field_name=field_name,
        operation=operation,
        value=value,
        value_status=value_status,
        expected_updated_at=(
            payload.expected_updated_at
        ),
        actor_id=actor_id,
    )
    return ExtractedFieldResponse.from_domain(field)


@api_router.post(
    "/receipts/{receipt_id}/verify",
    operation_id="verifyReceipt",
    response_model=ReceiptDetailResponse,
    responses={
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
        **VALIDATION_RESPONSE,
    },
)
async def verify_receipt(
    receipt_id: UUID,
    payload: VerifyReceiptRequest,
    verification: VerificationServiceDependency,
    receipt_queries: ReceiptQueryServiceDependency,
    actor_id: ActorIdDependency,
) -> ReceiptDetailResponse:
    await verification.verify_receipt(
        receipt_id=receipt_id,
        expected_updated_at=(
            payload.expected_updated_at
        ),
        actor_id=actor_id,
    )

    detail = await receipt_queries.get_receipt(
        receipt_id=receipt_id
    )
    return ReceiptDetailResponse.from_domain(detail)


@api_router.get(
    "/receipts/{receipt_id}/history",
    operation_id="getReceiptHistory",
    response_model=list[CorrectionHistoryResponse],
    responses=NOT_FOUND_RESPONSE,
)
async def get_receipt_history(
    receipt_id: UUID,
    service: HistoryServiceDependency,
) -> list[CorrectionHistoryResponse]:
    history = await service.get_correction_history(
        receipt_id=receipt_id
    )
    return [
        CorrectionHistoryResponse.from_domain(record)
        for record in history
    ]