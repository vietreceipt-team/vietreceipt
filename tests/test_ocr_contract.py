import csv
import json
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from scripts.run_baseline import (
    PROJECT_ROOT,
    build_ocr_result,
    load_validator,
    validate_ocr_result,
)


class OCRContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt_id = UUID("31915ef1-6fb4-4e7d-b6f5-53be51c50e3d")
        self.ocr_run_id = UUID("b3ac8bb4-6383-4b97-9911-5a6900054608")
        self.validator = load_validator()

    def test_adapter_emits_canonical_v13(self) -> None:
        document = build_ocr_result(
            {
                "rec_texts": ["  MINIMART ANAN  "],
                "rec_scores": [0.9876543],
                "rec_polys": [[[90, 30], [10, 30], [10, 10], [90, 10]]],
            },
            receipt_id=self.receipt_id,
            ocr_run_id=self.ocr_run_id,
            width_px=100,
            height_px=50,
            duration_ms=42,
        )

        validate_ocr_result(document, self.validator)
        self.assertEqual(document["schema_version"], "1.3")
        self.assertEqual(document["blocks"][0]["block_id"], "block_0")
        self.assertEqual(document["blocks"][0]["text"], "MINIMART ANAN")
        self.assertEqual(
            document["blocks"][0]["polygon"],
            [
                {"x": 0.1, "y": 0.2},
                {"x": 0.9, "y": 0.2},
                {"x": 0.9, "y": 0.6},
                {"x": 0.1, "y": 0.6},
            ],
        )

    def test_missing_polygon_fails_instead_of_emitting_invalid_block(self) -> None:
        with self.assertRaisesRegex(ValueError, "every recognized text"):
            build_ocr_result(
                {"rec_texts": ["text"], "rec_scores": [0.9], "rec_polys": []},
                receipt_id=self.receipt_id,
                ocr_run_id=self.ocr_run_id,
                width_px=100,
                height_px=50,
                duration_ms=1,
            )

    def test_unknown_property_is_rejected(self) -> None:
        document = build_ocr_result(
            {"rec_texts": [], "rec_scores": [], "rec_polys": []},
            receipt_id=self.receipt_id,
            ocr_run_id=self.ocr_run_id,
            width_px=100,
            height_px=50,
            duration_ms=1,
        )
        document["timestamp"] = "2026-08-13T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "validation failed"):
            validate_ocr_result(document, self.validator)

    def test_all_committed_benchmark_outputs_match_mapping_and_contract(self) -> None:
        mapping_path = PROJECT_ROOT / "results" / "benchmark_run_mapping.csv"
        with mapping_path.open(encoding="utf-8", newline="") as handle:
            mapping_rows = list(csv.DictReader(handle))

        expected_ids = [f"R{index:03d}" for index in range(1, 41)]
        self.assertEqual([row["test_id"] for row in mapping_rows], expected_ids)

        for row in mapping_rows:
            sample_id = row["test_id"]
            with self.subTest(sample_id=sample_id):
                output_path = (PROJECT_ROOT / row["output_file"]).resolve()
                self.assertTrue(output_path.is_relative_to(PROJECT_ROOT.resolve()))
                self.assertTrue(output_path.is_file(), f"missing {output_path}")

                with output_path.open(encoding="utf-8") as handle:
                    document = json.load(handle)

                validate_ocr_result(document, self.validator)
                self.assertEqual(document["receipt_id"], row["receipt_id"])
                self.assertEqual(document["ocr_run_id"], row["ocr_run_id"])

                blocks = document["blocks"]
                block_ids = [block["block_id"] for block in blocks]
                reading_order = [block["reading_order"] for block in blocks]
                self.assertEqual(len(block_ids), len(set(block_ids)))
                self.assertEqual(reading_order, list(range(len(blocks))))
                for block in blocks:
                    self.assertEqual(len(block["polygon"]), 4)
                    for point in block["polygon"]:
                        self.assertGreaterEqual(point["x"], 0)
                        self.assertLessEqual(point["x"], 1)
                        self.assertGreaterEqual(point["y"], 0)
                        self.assertLessEqual(point["y"], 1)


if __name__ == "__main__":
    unittest.main()
