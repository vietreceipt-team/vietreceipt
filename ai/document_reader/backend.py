"""Optional TV5 adapter. Core reader does not depend on FastAPI/backend."""

import os

from .pipeline import ReaderError, read_document as core_read_document


def read_document(data, *, content_type, receipt_id, ocr_run_id):
    mode = os.getenv("V2_READER_ISOLATION", "subprocess")
    if mode == "subprocess":
        from backend.app.v2.reader_isolation import read_isolated

        return read_isolated(
            data,
            content_type=content_type,
            receipt_id=receipt_id,
            ocr_run_id=ocr_run_id,
        )
    if mode != "inprocess":
        from backend.app.v2.errors import V2Error

        raise V2Error(
            "INVALID_READER_CONFIG",
            "Reader isolation must be subprocess or inprocess.",
            503,
            False,
        )
    try:
        return core_read_document(
            data,
            content_type=content_type,
            receipt_id=receipt_id,
            ocr_run_id=ocr_run_id,
        )
    except ReaderError as exc:
        from backend.app.v2.errors import V2Error

        raise V2Error(
            exc.code, str(exc), 503 if exc.retryable else 422, exc.retryable
        ) from exc
