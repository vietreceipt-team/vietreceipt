import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from PIL import Image

from ai.ocr.artifacts import ImmutableOCRArtifactStore
from ai.ocr.contract import validate_ocr_result
from ai.ocr.pipeline import OCRPipeline, build_ocr_result, run_ocr


class FakeOCREngine:
    def __init__(self, *, polygon=None) -> None:
        self.polygon = polygon or [[0, 0], [80, 0], [80, 20], [0, 20]]
        self.predict_calls = 0

    def predict(self, _image):
        self.predict_calls += 1
        return [
            {
                "rec_texts": ["MINIMART"],
                "rec_scores": [0.98],
                "rec_polys": [self.polygon],
            }
        ]


def canonical_document(*, receipt_id=None, ocr_run_id=None):
    return build_ocr_result(
        {
            "rec_texts": ["MINIMART", "123.000 VND"],
            "rec_scores": [0.98, 0.95],
            "rec_polys": [
                [[0, 0], [80, 0], [80, 20], [0, 20]],
                [[0, 30], [80, 30], [80, 50], [0, 50]],
            ],
        },
        receipt_id=receipt_id or uuid4(),
        ocr_run_id=ocr_run_id or uuid4(),
        width_px=100,
        height_px=60,
        duration_ms=2,
    )


class OCRWeek2PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt_id = UUID("31915ef1-6fb4-4e7d-b6f5-53be51c50e3d")
        self.run_id = UUID("b3ac8bb4-6383-4b97-9911-5a6900054608")
        self.image = Image.new("RGB", (100, 60), "white")

    def tearDown(self) -> None:
        self.image.close()

    def test_integration_entry_point_accepts_backend_uuids_and_validates(self) -> None:
        result = OCRPipeline(FakeOCREngine()).run_ocr(
            self.image,
            receipt_id=str(self.receipt_id),
            ocr_run_id=str(self.run_id),
        )
        validate_ocr_result(result)
        self.assertEqual(result["receipt_id"], str(self.receipt_id))
        self.assertEqual(result["ocr_run_id"], str(self.run_id))

    def test_same_receipt_reprocess_uses_new_run_id(self) -> None:
        pipeline = OCRPipeline(FakeOCREngine())
        first = pipeline.run_ocr(
            self.image, receipt_id=self.receipt_id, ocr_run_id=uuid4()
        )
        second = pipeline.run_ocr(
            self.image, receipt_id=self.receipt_id, ocr_run_id=uuid4()
        )
        self.assertEqual(first["receipt_id"], second["receipt_id"])
        self.assertNotEqual(first["ocr_run_id"], second["ocr_run_id"])

    def test_worker_provider_reuses_one_engine_across_receipts(self) -> None:
        created_engines = []

        def engine_factory():
            engine = FakeOCREngine()
            created_engines.append(engine)
            return engine

        worker_pipeline = OCRPipeline(engine_factory=engine_factory)
        second_receipt_id = uuid4()
        first_run_id = uuid4()
        second_run_id = uuid4()

        with patch("ai.ocr.pipeline._worker_pipeline", worker_pipeline):
            first = run_ocr(
                self.image,
                receipt_id=self.receipt_id,
                ocr_run_id=first_run_id,
            )
            second = run_ocr(
                self.image,
                receipt_id=second_receipt_id,
                ocr_run_id=second_run_id,
            )

        self.assertEqual(len(created_engines), 1)
        self.assertEqual(created_engines[0].predict_calls, 2)
        self.assertEqual(first["receipt_id"], str(self.receipt_id))
        self.assertEqual(first["ocr_run_id"], str(first_run_id))
        self.assertEqual(second["receipt_id"], str(second_receipt_id))
        self.assertEqual(second["ocr_run_id"], str(second_run_id))

    def test_immutable_store_preserves_previous_run_and_rejects_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ImmutableOCRArtifactStore(Path(temp_dir))
            first = canonical_document(receipt_id=self.receipt_id)
            second = canonical_document(receipt_id=self.receipt_id)
            first_path = store.write(first)
            second_path = store.write(second)

            self.assertNotEqual(first_path, second_path)
            self.assertTrue(first_path.exists())
            self.assertTrue(second_path.exists())
            with self.assertRaisesRegex(FileExistsError, "Refusing to overwrite"):
                store.write(first)
            self.assertEqual(json.loads(first_path.read_text(encoding="utf-8")), first)

    def test_benchmark_identifier_cannot_leak_into_runtime_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "Backend-style UUID"):
            OCRPipeline(FakeOCREngine()).run_ocr(
                self.image, receipt_id="R001", ocr_run_id=self.run_id
            )

    def test_missing_or_malformed_polygon_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "four-point polygon"):
            OCRPipeline(FakeOCREngine(polygon=[[0, 0], [80, 0], [80, 20]])).run_ocr(
                self.image, receipt_id=self.receipt_id, ocr_run_id=self.run_id
            )


class OCRWeek2InvariantTests(unittest.TestCase):
    def test_duplicate_block_ids_fail_validation(self) -> None:
        document = canonical_document()
        document["blocks"][1]["block_id"] = document["blocks"][0]["block_id"]
        with self.assertRaisesRegex(ValueError, "block_id values must be unique"):
            validate_ocr_result(document)

    def test_reading_order_must_be_zero_based_and_contiguous(self) -> None:
        document = canonical_document()
        document["blocks"][1]["reading_order"] = 3
        with self.assertRaisesRegex(ValueError, "reading_order must be contiguous"):
            validate_ocr_result(document)

    def test_polygon_coordinates_must_be_normalized(self) -> None:
        document = canonical_document()
        document["blocks"][0]["polygon"][0]["x"] = 1.1
        with self.assertRaisesRegex(ValueError, "maximum of 1"):
            validate_ocr_result(document)

    def test_polygon_point_order_must_be_tl_tr_br_bl(self) -> None:
        document = canonical_document()
        document["blocks"][0]["polygon"].reverse()
        with self.assertRaisesRegex(ValueError, "TL, TR, BR, BL"):
            validate_ocr_result(document)


if __name__ == "__main__":
    unittest.main()
