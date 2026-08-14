"""Integration-ready VietReceipt OCR package."""

from .artifacts import ImmutableOCRArtifactStore
from .contract import load_ocr_validator, validate_ocr_result
from .pipeline import OCRPipeline, build_ocr_result, create_paddleocr_engine, run_ocr

__all__ = [
    "ImmutableOCRArtifactStore",
    "OCRPipeline",
    "build_ocr_result",
    "create_paddleocr_engine",
    "load_ocr_validator",
    "run_ocr",
    "validate_ocr_result",
]
