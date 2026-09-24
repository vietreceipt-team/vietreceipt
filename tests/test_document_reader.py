import io
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from uuid import uuid4

import pypdfium2 as pdfium
from PIL import Image

from ai.document_reader import DocumentReader, ReaderConfig, ReaderError
from ai.document_reader.contract import validate_document
from ai.document_reader.pipeline import _restore_point
from ai.ocr.pipeline import OCRPipeline

HAS_PDF_FIXTURE_DEPS = importlib.util.find_spec("reportlab") is not None


def make_text_pdf(*args, **kwargs):
    from scripts.create_document_fixtures import make_text_pdf as build

    return build(*args, **kwargs)


def scan_pdf(*args, **kwargs):
    from scripts.create_document_fixtures import scan_pdf as build

    return build(*args, **kwargs)


class Engine:
    """Explicit test provider; PDF extraction and rendering remain real."""

    def __init__(self):
        self.calls = 0

    def predict(self, image):
        self.calls += 1
        h, w = image.shape[:2]
        return [
            {
                "rec_texts": ["TEST INVOICE"],
                "rec_scores": [0.9],
                "rec_polys": [
                    [
                        [w * 0.1, h * 0.1],
                        [w * 0.8, h * 0.1],
                        [w * 0.8, h * 0.2],
                        [w * 0.1, h * 0.2],
                    ]
                ],
            }
        ]


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.reader = DocumentReader(
            config=ReaderConfig(orientation="none"), ocr=OCRPipeline(self.engine)
        )
        self.ids = dict(receipt_id=uuid4(), ocr_run_id=uuid4())

    def read(self, data, mime="application/pdf", reader=None):
        return (reader or self.reader).process(data, content_type=mime, **self.ids)

    def png(self, size=(120, 200)):
        stream = io.BytesIO()
        Image.new("RGB", size, "white").save(stream, format="PNG")
        return stream.getvalue()

    def test_image(self):
        result = self.read(self.png(), "image/png")
        validate_document(result)
        self.assertEqual(
            result["pages"][0]["evidence"]["blocks"][0]["block_id"], "p0_b000000"
        )

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_text_pdf_avoids_ocr_and_keeps_order(self):
        text = "INVOICE DEMONSTRATION ABCDEFG 123456789"
        result = self.read(make_text_pdf([text]))
        blocks = result["pages"][0]["evidence"]["blocks"]
        self.assertEqual(" ".join(b["text"] for b in blocks), text)
        self.assertEqual(self.engine.calls, 0)

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_pdf_geometry_matches_unrotated_viewport(self):
        from contextlib import closing

        data = make_text_pdf(["INVOICE DEMONSTRATION ABCDEFG 123456789"])
        with pdfium.PdfDocument(data) as pdf:
            with closing(pdf[0]) as page:
                page.set_rotation(90)
            stream = io.BytesIO()
            pdf.save(stream)
        original = self.read(data)
        rotated = self.read(stream.getvalue())
        a = original["pages"][0]["evidence"]["blocks"]
        b = rotated["pages"][0]["evidence"]["blocks"]
        self.assertEqual(a, b)
        self.assertAlmostEqual(a[0]["polygon"][0]["x"], 35 / 640, delta=0.01)
        self.assertLess(a[0]["polygon"][0]["y"], 0.07)

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_blank_pdf_falls_back_to_empty_ocr(self):
        class Empty:
            def predict(self, image):
                return []

        reader = DocumentReader(
            config=ReaderConfig(orientation="none"), ocr=OCRPipeline(Empty())
        )
        result = self.read(make_text_pdf([]), reader=reader)
        self.assertEqual(result["pages"][0]["evidence"]["blocks"], [])

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_multilingual_text(self):
        fonts = [
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        font = next((p for p in fonts if p.exists()), None)
        if not font:
            self.skipTest("Unicode fixture font unavailable")
        text = "CÔNG TY MẪU VIETRECEIPT Tổng thanh toán 143.000 VND"
        result = self.read(make_text_pdf([text], font_path=font))
        actual = " ".join(b["text"] for b in result["pages"][0]["evidence"]["blocks"])
        self.assertEqual(actual, text)

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_scan_uses_ocr(self):
        result = self.read(scan_pdf(Image.new("RGB", (640, 820), "white")))
        self.assertEqual(self.engine.calls, 1)
        self.assertEqual(result["pages"][0]["evidence"]["engine"]["name"], "paddleocr")

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_mixed_pdf_routing(self):
        with (
            pdfium.PdfDocument(
                make_text_pdf(["INVOICE DEMONSTRATION ABCDEFG 123456789"])
            ) as text,
            pdfium.PdfDocument(scan_pdf(Image.new("RGB", (640, 820), "white"))) as scan,
        ):
            text.import_pages(scan)
            stream = io.BytesIO()
            text.save(stream)
        result = self.read(stream.getvalue())
        self.assertEqual(len(result["pages"]), 2)
        self.assertEqual(self.engine.calls, 1)
        validate_document(result)

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_multi_page_ids_and_provenance(self):
        data = make_text_pdf(["INVOICE DEMONSTRATION ABCDEFG 123456789"], pages=2)
        first = self.read(data)
        self.ids["ocr_run_id"] = uuid4()
        second = self.read(data)
        validate_document(first)
        self.assertNotEqual(first["ocr_run_id"], second["ocr_run_id"])
        for a, b in zip(first["pages"], second["pages"]):
            self.assertEqual(a["evidence"]["blocks"], b["evidence"]["blocks"])

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_duplicate_block_across_pages_rejected(self):
        result = self.read(
            make_text_pdf(["INVOICE DEMONSTRATION ABCDEFG 123456789"], pages=2)
        )
        result["pages"][1]["evidence"]["blocks"][0]["block_id"] = result["pages"][0][
            "evidence"
        ]["blocks"][0]["block_id"]
        with self.assertRaises(ValueError):
            validate_document(result)

    def test_page_index_rejected(self):
        result = self.read(self.png(), "image/png")
        result["pages"][0]["page_index"] = 1
        with self.assertRaises(ValueError):
            validate_document(result)

    def test_corrupt_pdf(self):
        with self.assertRaises(ReaderError) as ctx:
            self.read(b"%PDF-1.7 broken")
        self.assertEqual(ctx.exception.code, "PDF_READ_FAILED")

    def test_invalid_inputs(self):
        for data, mime in [
            (b"", "image/png"),
            (b"abc", "image/png"),
            (self.png(), "image/jpeg"),
            (self.png(), "text/plain"),
            (self.png(), "application/pdf"),
        ]:
            with (
                self.subTest(mime=mime, data=data[:10]),
                self.assertRaises(ReaderError),
            ):
                self.read(data, mime)

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_resource_limits(self):
        for config, data, mime in [
            (ReaderConfig(max_bytes=10), self.png(), "image/png"),
            (ReaderConfig(max_pixels=10), self.png(), "image/png"),
            (
                ReaderConfig(max_pages=1),
                make_text_pdf(["HELLO WORLD"], pages=2),
                "application/pdf",
            ),
        ]:
            with self.subTest(config=config), self.assertRaises(ReaderError):
                self.read(data, mime, DocumentReader(config=config))

    def test_blank_image_is_valid_empty_evidence(self):
        class Empty:
            def predict(self, image):
                return []

        reader = DocumentReader(
            config=ReaderConfig(orientation="none"), ocr=OCRPipeline(Empty())
        )
        result = self.read(self.png(), "image/png", reader)
        self.assertEqual(result["pages"][0]["evidence"]["blocks"], [])

    def test_orientation_trials_and_inverse_mapping(self):
        class Orientation:
            def predict(self, image):
                return [{"label_names": ["90"], "scores": [0.99]}]

        reader = DocumentReader(
            ocr=OCRPipeline(self.engine), orientation_model=Orientation()
        )
        self.read(self.png(), "image/png", reader)
        self.assertEqual(self.engine.calls, 1)
        for angle, point in [
            (0, (0.2, 0.3)),
            (90, (0.3, 0.8)),
            (180, (0.8, 0.7)),
            (270, (0.7, 0.2)),
        ]:
            with self.subTest(angle=angle):
                for actual, expected in zip(_restore_point(0.2, 0.3, angle), point):
                    self.assertAlmostEqual(actual, expected)

    def test_exif_dimensions(self):
        stream = io.BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (120, 200), "white").save(stream, format="JPEG", exif=exif)
        result = self.read(stream.getvalue(), "image/jpeg")
        self.assertEqual(
            result["pages"][0]["evidence"]["image"], {"width_px": 200, "height_px": 120}
        )

    def test_resize_keeps_source_dimensions(self):
        reader = DocumentReader(
            config=ReaderConfig(orientation="none", max_side=100, contrast=1.2),
            ocr=OCRPipeline(self.engine),
        )
        result = self.read(self.png(), "image/png", reader)
        self.assertEqual(
            result["pages"][0]["evidence"]["image"], {"width_px": 120, "height_px": 200}
        )

    def test_typed_ocr_failure(self):
        class Broken:
            def predict(self, image):
                raise RuntimeError("internal private detail")

        reader = DocumentReader(
            config=ReaderConfig(orientation="none"), ocr=OCRPipeline(Broken())
        )
        with self.assertRaises(ReaderError) as ctx:
            self.read(self.png(), "image/png", reader)
        self.assertEqual(ctx.exception.code, "OCR_FAILED")
        self.assertNotIn("private", str(ctx.exception))

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_force_pdf_ocr_ablation(self):
        reader = DocumentReader(
            config=ReaderConfig(orientation="none", force_pdf_ocr=True),
            ocr=OCRPipeline(self.engine),
        )
        self.read(
            make_text_pdf(["INVOICE DEMONSTRATION ABCDEFG 123456789"]), reader=reader
        )
        self.assertEqual(self.engine.calls, 1)

    def test_bad_orientation_is_typed(self):
        class BadOrientation:
            def predict(self, image):
                return [{"label_names": ["45"], "scores": [0.9]}]

        reader = DocumentReader(
            ocr=OCRPipeline(self.engine), orientation_model=BadOrientation()
        )
        with self.assertRaises(ReaderError) as ctx:
            self.read(self.png(), "image/png", reader)
        self.assertEqual(ctx.exception.code, "ORIENTATION_FAILED")

    @unittest.skipUnless(HAS_PDF_FIXTURE_DEPS, "reportlab test dependency unavailable")
    def test_benchmark_keeps_failures_and_missing_references(self):
        from scripts.benchmark_document_reader import benchmark

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bad.pdf").write_bytes(b"%PDF-1.7 broken")
            (root / "good.pdf").write_bytes(
                make_text_pdf(["INVOICE DEMONSTRATION ABCDEFG 123456789"])
            )
            manifest = {
                "dataset": "unit-test",
                "split": "development",
                "version": "1",
                "samples": [
                    {"id": "bad", "path": "bad.pdf", "reference": "ABC"},
                    {"id": "good", "path": "good.pdf"},
                ],
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with patch(
                "scripts.benchmark_document_reader.DocumentReader",
                return_value=self.reader,
            ):
                report = benchmark(path, root / "run", ReaderConfig(orientation="none"))
                self.assertEqual(report["samples"][0]["cer"], 1)
                self.assertIsNone(report["samples"][1]["cer"])
                self.assertEqual(report["slices"]["all"]["failures"], 1)
                self.assertEqual(report["slices"]["all"]["referenced"], 1)
                with self.assertRaises(FileExistsError):
                    benchmark(path, root / "run", ReaderConfig(orientation="none"))


if __name__ == "__main__":
    unittest.main()
