from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.api.dependencies import (
    ApplicationServicesUnavailable,
)
from backend.app.domain.errors import (
    DomainError,
    FieldNotFound,
    InvalidFieldValue,
    InvalidReceiptState,
    PersistenceFailure,
    ReceiptNotFound,
    SchedulingFailure,
    StaleUpdate,
    VerificationFailure,
)


def get_request_id(request: Request) -> UUID:
    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    if isinstance(request_id, UUID):
        return request_id

    return uuid4()


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: UUID,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                    "request_id": request_id,
                }
            }
        ),
    )


async def domain_error_handler(
    request: Request,
    error: DomainError,
) -> JSONResponse:
    details: dict[str, Any] = {}

    if isinstance(error, InvalidReceiptState):
        details["current_status"] = (
            error.current_status.value
        )

        if error.target_status is not None:
            details["target_status"] = (
                error.target_status.value
            )

        if error.operation is not None:
            details["operation"] = error.operation

    if isinstance(error, InvalidFieldValue):
        details["field_name"] = error.field_name.value
        details["reason"] = error.reason

    if isinstance(
        error,
        (ReceiptNotFound, FieldNotFound),
    ):
        status_code = 404
    elif isinstance(
        error,
        (InvalidReceiptState, StaleUpdate),
    ):
        status_code = 409
    elif isinstance(
        error,
        (InvalidFieldValue, VerificationFailure),
    ):
        status_code = 422
    elif isinstance(
        error,
        (PersistenceFailure, SchedulingFailure),
    ):
        status_code = 503
    else:
        status_code = 500

    return error_response(
        status_code=status_code,
        code=error.code,
        message=error.message,
        request_id=get_request_id(request),
        details=details or None,
    )


async def request_validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    return error_response(
        status_code=422,
        code="REQUEST_VALIDATION_ERROR",
        message="Request validation failed.",
        request_id=get_request_id(request),
        details={
            "errors": jsonable_encoder(error.errors())
        },
    )


async def services_unavailable_handler(
    request: Request,
    error: ApplicationServicesUnavailable,
) -> JSONResponse:
    return error_response(
        status_code=503,
        code="APPLICATION_SERVICES_UNAVAILABLE",
        message=str(error),
        request_id=get_request_id(request),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        DomainError,
        domain_error_handler,
    )
    app.add_exception_handler(
        RequestValidationError,
        request_validation_error_handler,
    )
    app.add_exception_handler(
        ApplicationServicesUnavailable,
        services_unavailable_handler,
    )