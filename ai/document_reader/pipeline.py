"""CPU document reader. No KIE rules, queue, persistence or dataset IDs."""

from __future__ import annotations

from contextlib import closing

import io
import math
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass
from importlib.metadata import version
from functools import partial
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

from ai.ocr.contract import order_polygon_points
from ai.ocr.pipeline import OCRPipeline, create_paddleocr_engine
from .contract import validate_document

_process_lock = threading.RLock()


class ReaderError(RuntimeError):
    """Safe failure message and machine-readable code for the worker boundary."""

    def __init__(self, code, message, *, retryable=False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ReaderConfig:
    dpi: int = 200
    max_bytes: int = 30 * 1024 * 1024
    max_pages: int = 30
    max_pixels: int = 40_000_000
    max_pdf_chars: int = 200_000
    min_pdf_chars: int = 20
    orientation: str = "auto"
    max_side: int = 0
    contrast: float = 1.0
    force_pdf_ocr: bool = False

    def __post_init__(self):
        if not 72 <= self.dpi <= 600:
            raise ValueError("dpi must be between 72 and 600")
        for name in (
            "max_bytes",
            "max_pages",
            "max_pixels",
            "max_pdf_chars",
            "min_pdf_chars",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.orientation not in ("none", "auto") or self.max_side < 0:
            raise ValueError("Invalid preprocessing configuration")
        if not math.isfinite(self.contrast) or not 0 < self.contrast <= 4:
            raise ValueError("contrast must be finite and in (0, 4]")


def _clean_text(text):
    # Preserve Vietnamese combining marks; drop non-transportable controls.
    return "".join(c for c in text if c in "\t\r\n" or unicodedata.category(c) != "Cc")


def _polygon(points, width, height):
    ordered = order_polygon_points([(x * width, y * height) for x, y in points])
    return [
        {
            "x": round(min(1, max(0, x / width)), 6),
            "y": round(min(1, max(0, y / height)), 6),
        }
        for x, y in ordered
    ]


def _restore_point(x, y, clockwise):
    return {0: (x, y), 90: (y, 1 - x), 180: (1 - x, 1 - y), 270: (1 - y, x)}[clockwise]


def _reading_order(blocks):
    """Cluster overlapping baselines before sorting left-to-right.

    Sorting raw glyph tops scrambles words with accents/capital letters.
    This is a row-major baseline, not semantic table/column reconstruction.
    """

    def bounds(block):
        return (
            min(p["x"] for p in block["polygon"]),
            min(p["y"] for p in block["polygon"]),
            max(p["y"] for p in block["polygon"]),
        )

    rows = []
    for block in sorted(blocks, key=lambda b: (bounds(b)[1], bounds(b)[0], b["text"])):
        x, top, bottom = bounds(block)
        match = next(
            (
                row
                for row in reversed(rows)
                if min(row[2], bottom) - max(row[1], top)
                > 0.45 * min(row[2] - row[1], bottom - top)
            ),
            None,
        )
        if match is None:
            rows.append(([block], top, bottom))
        else:
            match[0].append(block)
    return [
        b
        for row, _, _ in rows
        for b in sorted(row, key=lambda b: (bounds(b)[0], b["text"]))
    ]


class DocumentReader:
    """One instance per process; serialized because PDFium/Paddle are not thread-safe.

    process_with_metadata returns audit metadata separately: the strict TV5 wire
    envelope cannot contain extra keys. No mutable last-run state is retained.
    """

    def __init__(self, *, config=None, ocr=None, orientation_model=None):
        self.config = config or ReaderConfig()
        # Per-line 180-degree correction hides document orientation and can make
        # an upside-down page score well while leaving the reading order reversed.
        self.ocr = (
            ocr
            if ocr is not None
            else OCRPipeline(
                engine_factory=partial(
                    create_paddleocr_engine, use_textline_orientation=False
                )
            )
        )
        self._lock = _process_lock
        self._orientation_model = orientation_model

    def process(self, data, *, content_type, receipt_id, ocr_run_id):
        return self.process_with_metadata(
            data,
            content_type=content_type,
            receipt_id=receipt_id,
            ocr_run_id=ocr_run_id,
        )[0]

    def process_with_metadata(self, data, *, content_type, receipt_id, ocr_run_id):
        receipt_id, ocr_run_id = str(UUID(str(receipt_id))), str(UUID(str(ocr_run_id)))
        if isinstance(data, (str, Path)):
            path = Path(data)
            if path.stat().st_size > self.config.max_bytes:
                raise ReaderError("INPUT_TOO_LARGE", "Document exceeds byte limit")
            data = path.read_bytes()
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise ReaderError("INVALID_FILE", "Expected nonempty image/PDF bytes")
        if len(data) > self.config.max_bytes:
            raise ReaderError("INPUT_TOO_LARGE", "Document exceeds byte limit")
        started = time.perf_counter()
        with self._lock:
            if content_type == "application/pdf":
                pages, metadata = self._pdf(bytes(data), receipt_id, ocr_run_id)
            elif content_type in ("image/png", "image/jpeg"):
                try:
                    with Image.open(io.BytesIO(data)) as source:
                        expected = {"image/png": "PNG", "image/jpeg": "JPEG"}[
                            content_type
                        ]
                        if source.format != expected:
                            raise ReaderError(
                                "INVALID_FILE",
                                "Image signature does not match MIME type",
                            )
                        self._check_size(*source.size)
                        image = ImageOps.exif_transpose(source).convert("RGB")
                    evidence, meta = self._image(image, receipt_id, ocr_run_id)
                    pages, metadata = [evidence], [dict(meta, source="IMAGE_OCR")]
                except (
                    UnidentifiedImageError,
                    OSError,
                    Image.DecompressionBombError,
                ) as exc:
                    raise ReaderError(
                        "INVALID_FILE", "Image cannot be decoded"
                    ) from exc
            else:
                raise ReaderError("UNSUPPORTED_MEDIA_TYPE", "Expected PNG, JPEG or PDF")
        for page_index, evidence in enumerate(pages):
            for index, block in enumerate(evidence["blocks"]):
                block["block_id"] = f"p{page_index}_b{index:06d}"
                block["reading_order"] = index
        result = {
            "schema_version": "document-2.0",
            "receipt_id": receipt_id,
            "ocr_run_id": ocr_run_id,
            "pages": [
                {"page_index": i, "evidence": page} for i, page in enumerate(pages)
            ],
        }
        try:
            validate_document(result)
        except ValueError as exc:
            raise ReaderError(
                "SCHEMA_VALIDATION_FAILED", "Reader produced invalid evidence"
            ) from exc
        return result, {
            "config": asdict(self.config),
            "pages": metadata,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

    def _check_size(self, width, height):
        if width <= 0 or height <= 0 or width * height > self.config.max_pixels:
            raise ReaderError(
                "IMAGE_SIZE_LIMIT", "Page dimensions exceed supported limits"
            )

    def _image(self, image, receipt_id, run_id):
        width, height = image.size
        self._check_size(width, height)
        if self.config.max_side and max(image.size) > self.config.max_side:
            image = image.copy()
            image.thumbnail((self.config.max_side, self.config.max_side))
        if self.config.contrast != 1:
            image = ImageEnhance.Contrast(image).enhance(self.config.contrast)
        angle, orientation_score = (
            self._orientation(image) if self.config.orientation == "auto" else (0, None)
        )
        rotated = image.rotate(-angle, expand=True) if angle else image
        try:
            result = self.ocr.run_ocr(rotated, receipt_id=receipt_id, ocr_run_id=run_id)
        except Exception as exc:
            raise ReaderError(
                "OCR_FAILED", "OCR engine failed; inspect worker diagnostics"
            ) from exc
        result["blocks"] = _reading_order(result["blocks"])
        for block in result["blocks"]:
            block["text"] = _clean_text(block["text"]).strip()
            block["polygon"] = _polygon(
                [_restore_point(p["x"], p["y"], angle) for p in block["polygon"]],
                width,
                height,
            )
        result["blocks"] = [b for b in result["blocks"] if b["text"]]
        result["image"] = {"width_px": width, "height_px": height}
        return result, {
            "orientation_clockwise": angle,
            "orientation_model": "PP-LCNet_x1_0_doc_ori"
            if self.config.orientation == "auto"
            else None,
            "orientation_score": orientation_score,
            "engine": result["engine"],
            "width_px": width,
            "height_px": height,
        }

    def _orientation(self, image):
        import numpy as np

        try:
            if self._orientation_model is None:
                from paddlex import create_model
                from paddlex.inference import PaddlePredictorOption
                from ai.ocr.pipeline import verify_runtime_versions

                verify_runtime_versions()
                self._orientation_model = create_model(
                    "PP-LCNet_x1_0_doc_ori",
                    device="cpu",
                    pp_option=PaddlePredictorOption(run_mode="paddle", cpu_threads=4),
                )
            predictions = list(
                self._orientation_model.predict(np.asarray(image)[:, :, ::-1])
            )
            label = int(predictions[0]["label_names"][0])
            score = float(predictions[0]["scores"][0])
            if (
                label not in (0, 90, 180, 270)
                or not math.isfinite(score)
                or not 0 <= score <= 1
            ):
                raise ValueError("Invalid orientation result")
            # Paddle label is the counterclockwise correction; internal geometry
            # helper expects the clockwise correction applied to the source.
            return (-label) % 360, score
        except Exception as exc:
            raise ReaderError(
                "ORIENTATION_FAILED", "Document orientation model failed"
            ) from exc

    def _pdf(self, data, receipt_id, run_id):
        import pypdfium2 as pdfium

        if not data[:1024].lstrip().startswith(b"%PDF-"):
            raise ReaderError("INVALID_FILE", "PDF signature is missing")
        try:
            document = pdfium.PdfDocument(data)
        except pdfium.PdfiumError as exc:
            raise ReaderError(
                "PDF_READ_FAILED", "PDF is corrupt or requires a password"
            ) from exc
        pages, metadata = [], []
        try:
            if not 0 < len(document) <= self.config.max_pages:
                raise ReaderError(
                    "PAGE_LIMIT", "PDF page count exceeds supported limits"
                )
            for index in range(len(document)):
                with closing(document[index]) as page:
                    # Canonical coordinates match PDF.js viewport rotation=0 in TV6.
                    intrinsic_rotation = page.get_rotation()
                    page.set_rotation(0)
                    width, height = page.get_size()
                    scale = self.config.dpi / 72
                    self._check_size(
                        math.ceil(width * scale), math.ceil(height * scale)
                    )
                    start = time.perf_counter()
                    blocks, usable = self._pdf_text(page)
                    if usable and not self.config.force_pdf_ocr:
                        evidence = {
                            "schema_version": "1.3",
                            "receipt_id": receipt_id,
                            "ocr_run_id": run_id,
                            "engine": {
                                "name": "pdfium-text",
                                "version": version("pypdfium2"),
                            },
                            "image": {
                                "width_px": math.ceil(width * scale),
                                "height_px": math.ceil(height * scale),
                            },
                            "blocks": blocks,
                            "average_confidence": 1.0,
                            "duration_ms": int((time.perf_counter() - start) * 1000),
                        }
                        meta = {
                            "source": "PDF_TEXT",
                            "confidence_semantics": "not_applicable_legacy_sentinel_1",
                        }
                    else:
                        try:
                            with closing(page.render(scale=scale)) as bitmap:
                                image = bitmap.to_pil().convert("RGB")
                        except Exception as exc:
                            raise ReaderError(
                                "PDF_RENDER_FAILED", "PDF page cannot be rendered"
                            ) from exc
                        evidence, meta = self._image(image, receipt_id, run_id)
                        meta["source"] = "PDF_OCR"
                    pages.append(evidence)
                    metadata.append(
                        dict(
                            meta,
                            page_index=index,
                            intrinsic_rotation=intrinsic_rotation,
                            renderer="pypdfium2",
                            renderer_version=version("pypdfium2"),
                            dpi=self.config.dpi,
                            color_mode="RGB",
                            canonical_rotation=0,
                        )
                    )
        except pdfium.PdfiumError as exc:
            raise ReaderError("PDF_READ_FAILED", "PDF page cannot be read") from exc
        finally:
            document.close()
        return pages, metadata

    def _pdf_text(self, page):
        left, bottom, right, top = page.get_bbox()
        width, height = right - left, top - bottom
        words, chars, boxes = [], [], []

        def flush():
            if chars and boxes:
                x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
                x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
                if x1 > x0 and y1 > y0:
                    words.append(
                        {
                            "text": "".join(chars),
                            "confidence": 1.0,
                            "polygon": _polygon(
                                [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], width, height
                            ),
                        }
                    )
            chars.clear()
            boxes.clear()

        with closing(page.get_textpage()) as textpage:
            count = textpage.count_chars()
            if count > self.config.max_pdf_chars:
                raise ReaderError("PDF_TEXT_LIMIT", "PDF text exceeds character limit")
            for index in range(count):
                char = textpage.get_text_range(index, 1)
                if not char or char.isspace():
                    flush()
                    continue
                if not _clean_text(char) or "\ufffd" in char:
                    flush()
                    continue
                x_left, b, r, t = textpage.get_charbox(index)
                if not all(math.isfinite(v) for v in (x_left, b, r, t)):
                    continue
                # Break discontinuous spans even if the PDF lacks spaces.
                box = (
                    (x_left - left) / width,
                    (top - t) / height,
                    (r - left) / width,
                    (top - b) / height,
                )
                if boxes and (
                    min(box[3], boxes[-1][3]) < max(box[1], boxes[-1][1]) - 0.003
                    or box[0] - boxes[-1][2] > 0.03
                ):
                    flush()
                chars.append(char)
                boxes.append(box)
            flush()
        words = _reading_order(words)
        text = "".join(b["text"] for b in words)
        usable = sum(c.isalnum() for c in text) >= self.config.min_pdf_chars
        # A large embedded scan with a small digital footer is not a text page.
        import pypdfium2.raw as raw

        for obj in page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE]):
            x_left, b, r, t = obj.get_bounds()
            if (r - x_left) * (t - b) > 0.5 * width * height and len(text) < 200:
                usable = False
        return words, usable


_reader = None
_reader_lock = threading.Lock()


def read_document(data, *, content_type, receipt_id, ocr_run_id):
    """Set V2_DOCUMENT_READER_CALLABLE=ai.document_reader:read_document."""
    global _reader
    with _reader_lock:
        if _reader is None:
            _reader = DocumentReader()
    return _reader.process(
        data, content_type=content_type, receipt_id=receipt_id, ocr_run_id=ocr_run_id
    )
