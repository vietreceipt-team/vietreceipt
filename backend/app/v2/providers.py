"""Callable seams owned by TV3/TV4; this module contains no extraction rules."""

import importlib
import os
from uuid import UUID

from .errors import V2Error


def load_callable(setting):
    path = os.getenv(setting, "")
    if not path:
        raise V2Error(
            "PROVIDER_NOT_CONFIGURED",
            f"{setting} must point to an integration-ready provider.",
            503,
            True,
        )
    try:
        module, name = path.split(":", 1)
        provider = getattr(importlib.import_module(module), name)
        if not callable(provider):
            raise TypeError()
        return provider
    except (ImportError, AttributeError, ValueError, TypeError) as exc:
        raise V2Error(
            "PROVIDER_NOT_CONFIGURED", f"{setting} is unavailable.", 503, True
        ) from exc


def configured_reader(data, *, content_type, receipt_id, ocr_run_id):
    return load_callable("V2_DOCUMENT_READER_CALLABLE")(
        data, content_type=content_type, receipt_id=receipt_id, ocr_run_id=ocr_run_id
    )


def configured_kie(evidence, *, kie_run_id):
    return load_callable("V2_KIE_CALLABLE")(evidence, kie_run_id=UUID(kie_run_id))


def image_ocr_reader(data, *, content_type, receipt_id, ocr_run_id):
    """Explicit opt-in for current TV3 image OCR. Does not pretend to read PDFs."""
    if content_type not in ("image/jpeg", "image/png"):
        raise V2Error(
            "PDF_READER_NOT_CONFIGURED",
            "Configure the TV3 PDF-capable document reader.",
            503,
            True,
        )
    from ai.ocr import run_ocr

    return run_ocr(data, receipt_id=receipt_id, ocr_run_id=ocr_run_id)
