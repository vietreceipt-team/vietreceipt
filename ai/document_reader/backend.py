"""Optional TV5 adapter. Core reader does not depend on FastAPI/backend."""

from .pipeline import ReaderError, read_document as core_read_document


def read_document(data, *, content_type, receipt_id, ocr_run_id):
    try:
        return core_read_document(
            data,
            content_type=content_type,
            receipt_id=receipt_id,
            ocr_run_id=ocr_run_id,
        )
    except ReaderError as exc:
        from app.v2.errors import V2Error

        raise V2Error(
            exc.code, str(exc), 503 if exc.retryable else 422, exc.retryable
        ) from exc
