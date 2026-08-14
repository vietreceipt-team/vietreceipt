"""Backend/worker-callable PaddleOCR pipeline returning canonical OCRResult v1.3."""

from __future__ import annotations

import io
import math
import os
import time
from collections.abc import Callable, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any, TypeAlias
from uuid import UUID

from PIL import Image, ImageOps

from .contract import order_polygon_points, validate_ocr_result

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "1.3"
PADDLEOCR_PACKAGE_VERSION = "3.0.3"
PADDLEPADDLE_VERSION = "3.0.0"
PADDLEX_VERSION = "3.0.3"
OCR_MODEL_VERSION = "PP-OCRv3"
OCR_LANGUAGE = "vi"

os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(PROJECT_ROOT / ".paddlex-cache"))

ImageInput: TypeAlias = str | Path | bytes | bytearray | Image.Image


def verify_runtime_versions() -> None:
    expected = {
        "paddlepaddle": PADDLEPADDLE_VERSION,
        "paddleocr": PADDLEOCR_PACKAGE_VERSION,
        "paddlex": PADDLEX_VERSION,
    }
    mismatches = [
        f"{package}={version(package)} (expected {expected_version})"
        for package, expected_version in expected.items()
        if version(package) != expected_version
    ]
    if mismatches:
        raise RuntimeError("Unpinned OCR runtime: " + "; ".join(mismatches))


def create_paddleocr_engine() -> Any:
    """Create the pinned Vietnamese PaddleOCR engine lazily."""
    from paddleocr import PaddleOCR

    verify_runtime_versions()
    return PaddleOCR(
        lang=OCR_LANGUAGE,
        ocr_version=OCR_MODEL_VERSION,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
        enable_mkldnn=False,
    )


def _require_uuid(value: UUID | str, name: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{name} must be a Backend-style UUID") from exc


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        payload = value
    elif hasattr(value, "json"):
        payload = value.json
    else:
        try:
            payload = dict(value)
        except (TypeError, ValueError) as exc:
            raise TypeError("Unsupported PaddleOCR result type") from exc

    if isinstance(payload, dict) and isinstance(payload.get("res"), dict):
        return payload["res"]
    if not isinstance(payload, dict):
        raise TypeError("PaddleOCR result did not contain an object")
    return payload


def _canonical_polygon(
    polygon: Sequence[Sequence[float]], width_px: int, height_px: int
) -> list[dict[str, float]]:
    if width_px < 1 or height_px < 1:
        raise ValueError("Image dimensions must be positive")
    ordered = order_polygon_points(polygon)
    return [
        {
            "x": round(min(1.0, max(0.0, x_px / width_px)), 6),
            "y": round(min(1.0, max(0.0, y_px / height_px)), 6),
        }
        for x_px, y_px in ordered
    ]


def build_ocr_result(
    raw_page: dict[str, Any],
    *,
    receipt_id: UUID | str,
    ocr_run_id: UUID | str,
    width_px: int,
    height_px: int,
    duration_ms: int,
) -> dict[str, Any]:
    """Adapt one engine page; callers validate before crossing a boundary."""
    canonical_receipt_id = _require_uuid(receipt_id, "receipt_id")
    canonical_run_id = _require_uuid(ocr_run_id, "ocr_run_id")
    texts = list(raw_page.get("rec_texts") or [])
    scores = list(raw_page.get("rec_scores") or [])
    polygons = list(raw_page.get("rec_polys") or [])

    if len(scores) < len(texts) or len(polygons) < len(texts):
        raise ValueError(
            "PaddleOCR output is incomplete: every recognized text needs a score "
            "and a four-point polygon"
        )

    blocks: list[dict[str, Any]] = []
    for source_index, raw_text in enumerate(texts):
        text = str(raw_text).strip()
        if not text:
            continue
        confidence = float(scores[source_index])
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Invalid confidence for OCR block {source_index}")

        reading_order = len(blocks)
        blocks.append(
            {
                "block_id": f"block_{reading_order}",
                "text": text,
                "confidence": round(confidence, 6),
                "polygon": _canonical_polygon(
                    polygons[source_index], width_px, height_px
                ),
                "reading_order": reading_order,
            }
        )

    average_confidence = (
        round(sum(block["confidence"] for block in blocks) / len(blocks), 6)
        if blocks
        else 0.0
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": str(canonical_receipt_id),
        "ocr_run_id": str(canonical_run_id),
        "engine": {"name": "paddleocr", "version": PADDLEOCR_PACKAGE_VERSION},
        "image": {"width_px": width_px, "height_px": height_px},
        "blocks": blocks,
        "average_confidence": average_confidence,
        "duration_ms": duration_ms,
    }


def _open_image(image: ImageInput) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.copy()
    if isinstance(image, (bytes, bytearray)):
        return Image.open(io.BytesIO(bytes(image)))
    path = Path(image).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")
    return Image.open(path)


class OCRPipeline:
    """Reusable OCR adapter; it owns inference but not persistence or receipt state."""

    def __init__(
        self,
        engine: Any | None = None,
        *,
        engine_factory: Callable[[], Any] = create_paddleocr_engine,
    ) -> None:
        self._engine = engine
        self._engine_factory = engine_factory

    @property
    def engine(self) -> Any:
        if self._engine is None:
            self._engine = self._engine_factory()
        return self._engine

    def run_ocr(
        self,
        image: ImageInput,
        *,
        receipt_id: UUID | str,
        ocr_run_id: UUID | str,
    ) -> dict[str, Any]:
        """Run OCR and return only a fully validated canonical document."""
        canonical_receipt_id = _require_uuid(receipt_id, "receipt_id")
        canonical_run_id = _require_uuid(ocr_run_id, "ocr_run_id")

        import numpy as np

        start_time = time.perf_counter()
        with _open_image(image) as source_image:
            oriented_image = ImageOps.exif_transpose(source_image).convert("RGB")
            width_px, height_px = oriented_image.size
            result_pages = list(self.engine.predict(np.asarray(oriented_image)))
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        raw_page = _as_mapping(result_pages[0]) if result_pages else {}
        document = build_ocr_result(
            raw_page,
            receipt_id=canonical_receipt_id,
            ocr_run_id=canonical_run_id,
            width_px=width_px,
            height_px=height_px,
            duration_ms=duration_ms,
        )
        validate_ocr_result(document)
        return document


def run_ocr(
    image: ImageInput,
    receipt_id: UUID | str,
    ocr_run_id: UUID | str,
    *,
    pipeline: OCRPipeline | None = None,
) -> dict[str, Any]:
    """Convenience integration entry point used by a worker/backend adapter."""
    return (pipeline or OCRPipeline()).run_ocr(
        image, receipt_id=receipt_id, ocr_run_id=ocr_run_id
    )
