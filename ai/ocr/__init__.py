"""Integration-ready VietReceipt OCR package."""

from .artifacts import ImmutableOCRArtifactStore
from .contract import load_ocr_validator, validate_ocr_result
from .pipeline import (
    OCRPipeline,
    build_ocr_result,
    create_paddleocr_engine,
    get_worker_ocr_pipeline,
    run_ocr,
)

__all__ = [
    "ImmutableOCRArtifactStore",
    "OCRPipeline",
    "build_ocr_result",
    "create_paddleocr_engine",
    "get_worker_ocr_pipeline",
    "load_ocr_validator",
    "run_ocr",
    "validate_ocr_result",
]
