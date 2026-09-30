from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr
from sqlalchemy.exc import SQLAlchemyError

from .errors import V2Error
from .schemas import ErrorResponse, InvoiceDetail, InvoicePage

router = APIRouter(
    prefix="/api/v2",
    tags=["Invoice V2"],
    responses={n: {"model": ErrorResponse} for n in (404, 409, 413, 422, 503)},
)


class VersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[StrictInt, Field(ge=1)]


class CorrectionRequest(VersionRequest):
    value: StrictStr | StrictInt | StrictFloat | None
    status: Literal["PRESENT", "NOT_PRESENT", "UNREADABLE", "AMBIGUOUS", "UNKNOWN"]


def service(request: Request):
    svc = getattr(request.app.state, "v2_service", None)
    if svc is None:
        raise V2Error(
            "BACKEND_NOT_CONFIGURED", "Invoice V2 persistence is not configured.", 503
        )
    return svc


@router.post("/receipts", status_code=201, response_model=InvoiceDetail)
def upload(
    file: Annotated[UploadFile, File()],
    svc=Depends(service),
    source_group: Annotated[
        Literal["PAPER_DIGITIZED", "IMAGE", "PDF"] | None, Form()
    ] = None,
):
    data = file.file.read(svc.max_upload_bytes + 1)
    return svc.upload(file.filename, file.content_type, data, source_group)


@router.get("/receipts", response_model=InvoicePage)
def list_receipts(
    svc=Depends(service),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return {"items": svc.list(limit, offset), "limit": limit, "offset": offset}


@router.get("/receipts/{receipt_id}", response_model=InvoiceDetail)
def detail(receipt_id: UUID, svc=Depends(service)):
    return svc.detail(str(receipt_id))


@router.get(
    "/receipts/{receipt_id}/source",
    response_class=Response,
    responses={
        200: {
            "content": {
                m: {"schema": {"type": "string", "format": "binary"}}
                for m in ("image/jpeg", "image/png", "application/pdf")
            }
        }
    },
)
def source(receipt_id: UUID, svc=Depends(service)):
    data, mime, name = svc.source(str(receipt_id))
    return Response(
        data,
        media_type=mime,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox",
        },
    )


@router.get("/receipts/{receipt_id}/evidence")
def evidence(receipt_id: UUID, svc=Depends(service)):
    from .models import MachineRun

    with svc.sessions() as s:
        inv = svc.get(s, str(receipt_id))
        run = (
            s.get(MachineRun, inv.latest_ocr_run_id) if inv.latest_ocr_run_id else None
        )
        return run.payload if run else None


@router.post(
    "/receipts/{receipt_id}/retry", status_code=202, response_model=InvoiceDetail
)
def retry(receipt_id: UUID, body: VersionRequest, svc=Depends(service)):
    return svc.retry(str(receipt_id), body.expected_version)


@router.patch(
    "/receipts/{receipt_id}/fields/{field}/correction", response_model=InvoiceDetail
)
def header_correction(
    receipt_id: UUID, field: str, body: CorrectionRequest, svc=Depends(service)
):
    return svc.correct(
        str(receipt_id),
        "header",
        "",
        field,
        body.value,
        body.status,
        body.expected_version,
    )


@router.patch(
    "/receipts/{receipt_id}/line-items/{line_id:path}/{field}/correction",
    response_model=InvoiceDetail,
)
def line_correction(
    receipt_id: UUID,
    line_id: str,
    field: str,
    body: CorrectionRequest,
    svc=Depends(service),
):
    return svc.correct(
        str(receipt_id),
        "line",
        line_id,
        field,
        body.value,
        body.status,
        body.expected_version,
    )


@router.patch(
    "/receipts/{receipt_id}/tax-groups/{tax_id}/{field}/correction",
    response_model=InvoiceDetail,
)
def tax_correction(
    receipt_id: UUID,
    tax_id: str,
    field: str,
    body: CorrectionRequest,
    svc=Depends(service),
):
    return svc.correct(
        str(receipt_id),
        "tax",
        tax_id,
        field,
        body.value,
        body.status,
        body.expected_version,
    )


@router.post("/receipts/{receipt_id}/verify", response_model=InvoiceDetail)
def verify(receipt_id: UUID, body: VersionRequest, svc=Depends(service)):
    return svc.verify(str(receipt_id), body.expected_version)


@router.get("/receipts/{receipt_id}/history")
def history(receipt_id: UUID, svc=Depends(service)):
    return svc.history(str(receipt_id))


@router.get(
    "/receipts/{receipt_id}/export",
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/json": {"schema": {"type": "object"}},
                "application/zip": {"schema": {"type": "string", "format": "binary"}},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {"type": "string", "format": "binary"}
                },
            }
        }
    },
)
def export(
    receipt_id: UUID, format: Literal["json", "csv", "xlsx"], svc=Depends(service)
):
    data, mime, name = svc.export(str(receipt_id), format)
    return Response(
        data,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/readiness")
def readiness(svc=Depends(service)):
    from sqlalchemy import select

    from .models import Invoice

    with svc.sessions() as s:
        s.execute(select(Invoice.receipt_id).limit(1))
    return {"status": "ready", "database": "ready"}


def register_v2(app):
    app.include_router(router)

    @app.exception_handler(V2Error)
    async def handle_v2(request, error):
        return JSONResponse(
            status_code=error.status,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "request_id": str(request.state.request_id),
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database(request, error):
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "PERSISTENCE_FAILED",
                    "message": "Database operation could not be completed.",
                    "request_id": str(request.state.request_id),
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request, error):
        import logging

        logging.getLogger(__name__).error(
            "Unexpected API error request_id=%s type=%s",
            request.state.request_id,
            type(error).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "The request could not be completed.",
                    "request_id": str(request.state.request_id),
                }
            },
        )
