import csv
import json
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from scripts.evaluate import evaluate
from scripts.run_baseline import build_ocr_result


class EvaluateTests(unittest.TestCase):
    def test_report_lists_coverage_and_missing_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = root / "manifest.csv"
            gt_dir = root / "ground_truth"
            ocr_dir = root / "ocr"
            report = root / "report.csv"
            gt_dir.mkdir()
            ocr_dir.mkdir()

            with manifest.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["test_id", "ground_truth_status"]
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {"test_id": "R001", "ground_truth_status": "annotated"},
                        {"test_id": "R002", "ground_truth_status": "not_started"},
                    ]
                )

            (gt_dir / "R001.txt").write_text("MINIMART ANAN", encoding="utf-8")
            document = build_ocr_result(
                {
                    "rec_texts": ["MINIMART ANAN"],
                    "rec_scores": [0.99],
                    "rec_polys": [[[0, 0], [100, 0], [100, 50], [0, 50]]],
                },
                receipt_id=UUID("31915ef1-6fb4-4e7d-b6f5-53be51c50e3d"),
                ocr_run_id=UUID("b3ac8bb4-6383-4b97-9911-5a6900054608"),
                width_px=100,
                height_px=50,
                duration_ms=1,
            )
            (ocr_dir / "R001.json").write_text(
                json.dumps(document), encoding="utf-8"
            )

            result = evaluate(
                manifest_path=manifest,
                gt_dir=gt_dir,
                ocr_dir=ocr_dir,
                report_path=report,
                schema_path=Path(__file__).parents[1]
                / "schemas"
                / "ocr-result.schema.json",
            )

            metadata = result["metadata"]
            self.assertEqual(metadata["status"], "INCOMPLETE")
            self.assertEqual(metadata["evaluated_sample_ids"], "R001")
            self.assertEqual(metadata["missing_sample_ids"], "R002")
            self.assertIn("whitespace", metadata["normalization_policy"])
            self.assertTrue(report.exists())


if __name__ == "__main__":
    unittest.main()
