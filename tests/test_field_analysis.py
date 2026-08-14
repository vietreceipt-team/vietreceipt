import json
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from ai.ocr.field_analysis import (
    CANONICAL_FIELDS,
    classify_field_error,
    evaluate_field_errors,
)
from ai.ocr.pipeline import build_ocr_result


RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000001")
REAL_RUN_ID = UUID("00000000-0000-4000-8000-000000000002")
ORACLE_RUN_ID = UUID("00000000-0000-4000-8000-000000000004")


def ocr_document(run_id, texts):
    polygons = [
        [[0, index * 10], [90, index * 10], [90, index * 10 + 8], [0, index * 10 + 8]]
        for index in range(len(texts))
    ]
    return build_ocr_result(
        {"rec_texts": texts, "rec_scores": [0.99] * len(texts), "rec_polys": polygons},
        receipt_id=RECEIPT_ID,
        ocr_run_id=run_id,
        width_px=100,
        height_px=100,
        duration_ms=1,
    )


def field(field_name, transcribed, normalized, source_ids, note=None):
    value = {
        "field_name": field_name,
        "annotation_status": "PRESENT",
        "transcribed_value": transcribed,
        "normalized_value": normalized,
        "source_block_ids": source_ids,
        "candidate_values": [],
        "annotator_note": note,
    }
    if field_name == "total_amount":
        value["currency"] = "VND"
    return value


def annotation_document():
    return {
        "record_type": "five-field-ground-truth-annotation",
        "annotation_schema_version": "1.0",
        "guideline_version": "1.1",
        "annotation_id": "00000000-0000-4000-8000-000000000003",
        "batch_id": "synthetic-week2-test",
        "dataset_snapshot": "synthetic-week2-test-v1",
        "example_only": True,
        "data_provenance": "synthetic test values; not benchmark or model output",
        "receipt_id": str(RECEIPT_ID),
        "source_ocr_run_id": str(REAL_RUN_ID),
        "annotator_id": "test-fixture",
        "annotated_at": None,
        "fields": {
            "merchant_name": field("merchant_name", "MINIMART", "MINIMART", ["block_0"]),
            "receipt_date": field(
                "receipt_date", "02/01/2020", "2020-01-02", ["block_1"]
            ),
            "total_amount": field(
                "total_amount", "123.000 VND", 123000, [], "OCR_OMISSION"
            ),
            "invoice_id": field(
                "invoice_id", "HD-0001", "HD-0001", ["block_3"], "OCR_SEGMENTATION: test fixture"
            ),
            "merchant_address": field(
                "merchant_address",
                "SO 1 DUONG MAU",
                "SO 1 DUONG MAU",
                ["block_4"],
                "OCR_GEOMETRY: test fixture",
            ),
        },
    }


class FieldAwareAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.real = ocr_document(
            REAL_RUN_ID,
            ["MINIMART", "02/O1/2020", "unrelated", "HD-0001", "SO 1 DUONG MAU"],
        )
        self.annotation = annotation_document()

    def test_evaluator_distinguishes_omission_substitution_and_not_ocr_error(self) -> None:
        fields = self.annotation["fields"]
        self.assertEqual(
            classify_field_error(fields["merchant_name"], self.real)["error_type"],
            "not_an_ocr_error",
        )
        self.assertEqual(
            classify_field_error(fields["receipt_date"], self.real)["error_type"],
            "ocr_substitution",
        )
        self.assertEqual(
            classify_field_error(fields["total_amount"], self.real)["error_type"],
            "ocr_omission",
        )

    def test_explicit_taxonomy_covers_grouping_reading_order_and_geometry(self) -> None:
        fields = self.annotation["fields"]
        self.assertEqual(
            classify_field_error(fields["invoice_id"], self.real)["error_type"],
            "ocr_segmentation_grouping",
        )
        self.assertEqual(
            classify_field_error(fields["merchant_address"], self.real)["error_type"],
            "ocr_geometry_evidence",
        )
        reading_order = dict(fields["merchant_name"])
        reading_order["annotator_note"] = "OCR_READING_ORDER: test fixture"
        self.assertEqual(
            classify_field_error(reading_order, self.real)["error_type"],
            "ocr_reading_order",
        )

    def test_report_records_provenance_oracle_support_slices_and_all_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            annotation_path = root / "annotation.json"
            real_path = root / "real.json"
            oracle_path = root / "oracle.json"
            manifest_path = root / "manifest.json"
            report_path = root / "report.json"
            annotation_path.write_text(
                json.dumps(self.annotation, ensure_ascii=False), encoding="utf-8"
            )
            real_path.write_text(json.dumps(self.real), encoding="utf-8")
            oracle_path.write_text(
                json.dumps(
                    ocr_document(
                        ORACLE_RUN_ID,
                        [
                            "MINIMART",
                            "02/01/2020",
                            "123.000 VND",
                            "HD-0001",
                            "SO 1 DUONG MAU",
                        ],
                    )
                ),
                encoding="utf-8",
            )
            manifest = {
                "dataset_version": "synthetic-week2-test-v1",
                "annotation_qa_state": "synthetic fixture",
                "example_only": True,
                "records": [
                    {
                        "test_id": "SYN001",
                        "selection_stratum": "challenge_low_contrast",
                        "annotation_path": annotation_path.name,
                        "real_ocr_path": real_path.name,
                        "oracle_ocr_path": oracle_path.name,
                    }
                ],
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            report = evaluate_field_errors(
                manifest_path=manifest_path,
                report_path=report_path,
                allow_examples=True,
                run_command="python tests synthetic field-aware fixture",
            )

            self.assertEqual(report["status"], "EXAMPLE_ONLY")
            self.assertEqual(
                [row["field_name"] for row in report["field_summaries"]],
                list(CANONICAL_FIELDS),
            )
            self.assertEqual(report["evaluated_field_count"], 5)
            self.assertEqual(report["oracle_ocr_available_count"], 1)
            self.assertEqual(
                report["quality_stratum_summaries"][0]["selection_stratum"],
                "challenge_low_contrast",
            )
            provenance = report["provenance"]
            for key in (
                "git_commit_sha",
                "paddleocr_package_version",
                "model_family",
                "language",
                "dataset_version",
                "annotation_qa_state",
                "run_command",
                "manifest_sha256",
            ):
                self.assertIn(key, provenance)
            self.assertTrue(report_path.exists())

    def test_non_example_report_covers_five_fields_even_before_gold_arrives(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            report_path = root / "report.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "dataset_version": "frozen-40-v1",
                        "annotation_qa_state": "pending KIE/Data field gold",
                        "example_only": False,
                        "records": [],
                    }
                ),
                encoding="utf-8",
            )
            report = evaluate_field_errors(
                manifest_path=manifest_path, report_path=report_path
            )
            self.assertEqual(
                report["status"], "WAITING_FOR_VERIFIED_FIELD_ANNOTATIONS"
            )
            self.assertEqual(len(report["field_summaries"]), 5)
            self.assertIsNotNone(report["dependency_note"])


if __name__ == "__main__":
    unittest.main()
