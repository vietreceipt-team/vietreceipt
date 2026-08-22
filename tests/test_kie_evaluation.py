from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai.kie.evaluation import (
    COMPLETED_STATUS,
    ERROR_TAXONOMY_DEFINITIONS,
    WAITING_STATUS,
    classify_root_cause,
    compute_field_metrics,
    evaluate_manifest,
    write_evaluation_report,
)


RECEIPT_ID = "11111111-1111-4111-8111-111111111111"
REAL_OCR_RUN_ID = "22222222-2222-4222-8222-222222222222"
ORACLE_OCR_RUN_ID = "33333333-3333-4333-8333-333333333333"


def make_empty_ocr(
    ocr_run_id: str,
) -> dict:
    return {
        "schema_version": "1.3",
        "receipt_id": RECEIPT_ID,
        "ocr_run_id": ocr_run_id,
        "engine": {
            "name": "synthetic-test-ocr",
            "version": "0.1.0",
        },
        "image": {
            "width_px": 1000,
            "height_px": 1600,
        },
        "blocks": [],
        "average_confidence": 0.0,
        "duration_ms": 10,
    }


def make_unknown_field(
    field_name: str,
) -> dict:
    field = {
        "field_name": field_name,
        "annotation_status": "UNKNOWN",
        "transcribed_value": None,
        "normalized_value": None,
        "source_block_ids": [],
        "candidate_values": [],
        "annotator_note": (
            "Synthetic unit-test fixture has no field evidence."
        ),
    }

    if field_name == "total_amount":
        field["currency"] = "VND"

    return field


def make_verified_annotation() -> dict:
    field_names = (
        "merchant_name",
        "receipt_date",
        "total_amount",
        "invoice_id",
        "merchant_address",
    )

    return {
        "record_type": (
            "five-field-ground-truth-annotation"
        ),
        "annotation_schema_version": "1.0",
        "guideline_version": "1.1",
        "annotation_id": (
            "44444444-4444-4444-8444-444444444444"
        ),
        "batch_id": "synthetic-unit-test",
        "dataset_snapshot": "synthetic-unit-test-v1",
        "example_only": False,
        "data_provenance": (
            "Synthetic values created only for evaluator unit tests."
        ),
        "receipt_id": RECEIPT_ID,
        "source_ocr_run_id": REAL_OCR_RUN_ID,
        "annotator_id": "synthetic-test-annotator",
        "annotated_at": "2026-08-22T00:00:00Z",
        "fields": {
            field_name: make_unknown_field(field_name)
            for field_name in field_names
        },
    }


def write_json(
    path: Path,
    document: dict,
) -> None:
    path.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_single_sample_split(
    path: Path,
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "test_id",
                "selection_stratum",
                "kie_split",
                "split_version",
                "split_seed",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "test_id": "T001",
                "selection_stratum": "synthetic_test",
                "kie_split": "development",
                "split_version": "synthetic-split-v1",
                "split_seed": "synthetic-seed",
            }
        )


def make_ready_fixture(
    root: Path,
) -> tuple[Path, Path, Path, Path, Path]:
    annotation_path = root / "annotation.json"
    real_path = root / "real.json"
    oracle_path = root / "oracle.json"
    manifest_path = root / "manifest.json"
    split_path = root / "split.csv"

    write_json(
        annotation_path,
        make_verified_annotation(),
    )
    write_json(
        real_path,
        make_empty_ocr(REAL_OCR_RUN_ID),
    )
    write_json(
        oracle_path,
        make_empty_ocr(ORACLE_OCR_RUN_ID),
    )
    write_single_sample_split(split_path)
    write_json(
        manifest_path,
        {
            "dataset_version": "synthetic-evaluator-test-v1",
            "annotation_qa_state": "VERIFIED",
            "annotation_provenance": (
                "Synthetic QA-complete evaluator unit-test fixture."
            ),
            "example_only": False,
            "records": [
                {
                    "test_id": "T001",
                    "annotation_path": str(annotation_path),
                    "real_ocr_path": str(real_path),
                    "oracle_ocr_path": str(oracle_path),
                    "oracle_qa_state": "VERIFIED",
                    "oracle_provenance": (
                        "Synthetic Oracle OCR unit-test fixture."
                    ),
                }
            ],
        },
    )

    return (
        manifest_path,
        split_path,
        annotation_path,
        real_path,
        oracle_path,
    )


class KIEMetricTests(unittest.TestCase):

    def test_required_root_cause_taxonomy_is_explicit(self) -> None:
        self.assertEqual(
            set(ERROR_TAXONOMY_DEFINITIONS),
            {
                "OCR_OMISSION",
                "OCR_SUBSTITUTION",
                "CANDIDATE_GENERATION_FAILURE",
                "CANDIDATE_RANKING_FAILURE",
                "NORMALIZATION_FAILURE",
                "AMBIGUITY",
                "ANNOTATION_ISSUE",
            },
        )

    def test_root_cause_uses_oracle_as_control(self) -> None:
        gold = {
            "annotation_status": "PRESENT",
            "normalized_value": "001238",
        }
        correct_oracle = {
            "value_status": "PRESENT",
            "predicted_value": "001238",
            "normalized_value": "001238",
            "review_reasons": [],
        }
        missing_real = {
            "value_status": "UNKNOWN",
            "predicted_value": None,
            "normalized_value": None,
            "review_reasons": ["NO_CANDIDATE"],
        }
        substituted_real = {
            "value_status": "PRESENT",
            "predicted_value": "001288",
            "normalized_value": "001288",
            "review_reasons": [],
        }
        missing_oracle = dict(missing_real)
        failed_normalization = {
            "value_status": "AMBIGUOUS",
            "predicted_value": "00I238",
            "normalized_value": None,
            "review_reasons": ["NORMALIZATION_FAILED"],
        }

        self.assertEqual(
            classify_root_cause(
                gold,
                missing_real,
                correct_oracle,
            ),
            "OCR_OMISSION",
        )
        self.assertEqual(
            classify_root_cause(
                gold,
                substituted_real,
                correct_oracle,
            ),
            "OCR_SUBSTITUTION",
        )
        self.assertEqual(
            classify_root_cause(
                gold,
                missing_real,
                missing_oracle,
            ),
            "CANDIDATE_GENERATION_FAILURE",
        )
        self.assertEqual(
            classify_root_cause(
                gold,
                failed_normalization,
                failed_normalization,
            ),
            "NORMALIZATION_FAILURE",
        )

    def test_field_metrics_distinguish_status_and_value_errors(
        self,
    ) -> None:
        annotation = {
            "fields": {
                "merchant_name": {
                    "annotation_status": "PRESENT",
                    "normalized_value": "STORE",
                },
                "receipt_date": {
                    "annotation_status": "PRESENT",
                    "normalized_value": "2026-08-22",
                },
                "total_amount": {
                    "annotation_status": "PRESENT",
                    "normalized_value": 325000,
                },
                "invoice_id": {
                    "annotation_status": "NOT_PRESENT",
                    "normalized_value": None,
                },
                "merchant_address": {
                    "annotation_status": "NOT_PRESENT",
                    "normalized_value": None,
                },
            }
        }
        kie_result = {
            "fields": {
                "merchant_name": {
                    "value_status": "PRESENT",
                    "normalized_value": "STORE",
                    "machine_needs_review": False,
                },
                "receipt_date": {
                    "value_status": "PRESENT",
                    "normalized_value": "2026-08-21",
                    "machine_needs_review": True,
                },
                "total_amount": {
                    "value_status": "UNKNOWN",
                    "normalized_value": None,
                    "machine_needs_review": True,
                },
                "invoice_id": {
                    "value_status": "PRESENT",
                    "normalized_value": "INV-1",
                    "machine_needs_review": False,
                },
                "merchant_address": {
                    "value_status": "NOT_PRESENT",
                    "normalized_value": None,
                    "machine_needs_review": True,
                },
            }
        }

        metrics = compute_field_metrics(
            [("T001", annotation, kie_result)]
        )

        self.assertEqual(metrics["sample_count"], 1)
        self.assertEqual(
            metrics["overall"]["decision_count"],
            5,
        )
        self.assertEqual(
            metrics["overall"]["exact_match_accuracy"],
            0.4,
        )
        self.assertEqual(
            metrics["overall"]["macro_exact_match"],
            0.4,
        )
        self.assertEqual(
            metrics["fields"]["receipt_date"]["error_count"],
            1,
        )
        self.assertEqual(
            metrics["overall"]["status_accuracy"],
            0.6,
        )
        self.assertEqual(
            metrics["overall"]["normalization_accuracy"],
            0.333333,
        )
        self.assertEqual(
            metrics["error_taxonomy"]["counts"],
            {
                "MISSED_PRESENT": 1,
                "NORMALIZATION_MISMATCH": 1,
                "SPURIOUS_PRESENT": 1,
            },
        )


class KIEEvaluatorTests(unittest.TestCase):

    def test_pending_manifest_returns_explicit_waiting_state(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = root / "manifest.json"
            split_path = root / "split.csv"
            write_single_sample_split(split_path)
            write_json(
                manifest_path,
                {
                    "dataset_version": "synthetic-pending-v1",
                    "annotation_qa_state": "PENDING",
                    "annotation_provenance": None,
                    "example_only": False,
                    "records": [],
                },
            )

            report = evaluate_manifest(
                manifest_path,
                split_path=split_path,
            )

            self.assertEqual(
                report["status"],
                WAITING_STATUS,
            )
            self.assertIsNone(report["metrics"])
            self.assertIsNone(report["modes"])
            self.assertEqual(
                report["sample_counts"]["evaluated"],
                0,
            )

    def test_verified_real_and_oracle_modes_complete_separately(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path, split_path, *_ = (
                make_ready_fixture(root)
            )

            report = evaluate_manifest(
                manifest_path,
                split_path=split_path,
            )

            self.assertEqual(
                report["status"],
                COMPLETED_STATUS,
            )
            self.assertEqual(
                report["sample_counts"]["evaluated"],
                1,
            )
            self.assertEqual(
                report["modes"]["real"]["all"][
                    "overall"
                ]["exact_match_accuracy"],
                1.0,
            )
            self.assertEqual(
                report["modes"]["oracle"]["all"][
                    "overall"
                ]["exact_match_accuracy"],
                1.0,
            )
            self.assertNotEqual(
                report["kie_runs"]["real"]["T001"][
                    "source_ocr_run_id"
                ],
                report["kie_runs"]["oracle"]["T001"][
                    "source_ocr_run_id"
                ],
            )
            self.assertEqual(
                report["propagation_gap"]["overall"][
                    "exact_match_accuracy"
                ],
                0.0,
            )
            self.assertEqual(
                report["error_analysis"]["all"]["counts"],
                {
                    category: 0
                    for category in ERROR_TAXONOMY_DEFINITIONS
                },
            )

            report_path = write_evaluation_report(
                report,
                root / "report.json",
            )
            self.assertEqual(
                json.loads(
                    report_path.read_text(encoding="utf-8")
                ),
                report,
            )

    def test_real_and_oracle_cannot_share_one_artifact(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (
                manifest_path,
                split_path,
                _,
                real_path,
                _,
            ) = make_ready_fixture(root)
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            manifest["records"][0][
                "oracle_ocr_path"
            ] = str(real_path)
            write_json(manifest_path, manifest)

            with self.assertRaisesRegex(
                ValueError,
                "different artifacts",
            ):
                evaluate_manifest(
                    manifest_path,
                    split_path=split_path,
                )

    def test_real_and_oracle_require_distinct_run_ids(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (
                manifest_path,
                split_path,
                _,
                _,
                oracle_path,
            ) = make_ready_fixture(root)
            write_json(
                oracle_path,
                make_empty_ocr(REAL_OCR_RUN_ID),
            )

            with self.assertRaisesRegex(
                ValueError,
                "different ocr_run_id",
            ):
                evaluate_manifest(
                    manifest_path,
                    split_path=split_path,
                )


if __name__ == "__main__":
    unittest.main()
