"""Evaluator protocol tests with synthetic, temporary gold; not thesis evaluation."""

import copy
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from jsonschema import ValidationError

from ai.kie.v2 import extract_invoice
from ai.kie.v2.config import (
    BASELINE_GROUPING,
    CONFIGURATION,
    GROUPING_CONFIGURATIONS,
    HEADER_FIELDS,
    INTERVAL_GROUPING,
    LINE_FIELDS,
)
from ai.kie.v2.evaluation import (
    VERSION,
    evaluate,
    metrics,
    row_matches,
    validate_gold,
)
from tests.kie_v2_fixtures import KIE_RUN, RECEIPT, invoice
from tests.kie_v2_grouping_fixtures import narrow_numbers


def gold_fixture():
    # Independently specified expected values for the synthetic fixture.
    values = [
        "01GTKT0/001",
        "AA/26E",
        "0000049",
        "2026-09-19",
        "Công ty Tổng Hợp Mẫu",
        "0101234567",
        "1 Đường Mẫu, Thành phố Mẫu",
        "Công ty Khách Mẫu",
        "0201234567",
        100000,
        8000,
        108000,
        "VND",
    ]
    ids = [0, 1, 2, 3, 4, 5, 6, 7, 8, 20, 21, 22, 9]

    def cell(value, block):
        return {
            "annotation_status": "PRESENT",
            "raw_value": str(value),
            "normalized_value": value,
            "source_block_ids": [f"p0_b{block}"],
        }

    return {
        "annotation_schema_version": "2.0",
        "receipt_id": RECEIPT,
        "dataset_family": "synthetic-unit-test",
        "dataset_snapshot": "fixture-1",
        "sample_id": "synthetic-49",
        "synthetic": True,
        "split": "validation",
        "mapping_version": "1",
        "fields": {f: cell(v, i) for f, v, i in zip(HEADER_FIELDS, values, ids)},
        "line_items": [
            {
                "line_id": "gold-A",
                **{
                    f: cell(v, i)
                    for f, v, i in zip(
                        LINE_FIELDS,
                        ["Dịch vụ mẫu", "gói", 2, 50000, 100000],
                        range(15, 20),
                    )
                },
            }
        ],
    }


class EvaluationV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kie-v2-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = invoice()
        self.gold = gold_fixture()
        self.manifest = {
            "dataset_family": "synthetic-unit-test",
            "dataset_snapshot": "fixture-1",
            "split": "validation",
            "synthetic": True,
            "template_regime": "synthetic-unit-only",
            "configuration": dict(CONFIGURATION),
            "frozen": True,
            "qa_status": "VERIFIED",
            "verified_by": "synthetic-test-double",
            "frozen_at": "2026-09-29T00:00:00Z",
            "sample_count": 1,
            "records": [],
        }

    def artifact(self, name, value):
        data = json.dumps(value).encode()
        (self.base / name).write_bytes(data)
        return {"path": name, "sha256": hashlib.sha256(data).hexdigest()}

    def prepare(self):
        self.manifest["records"] = [
            {
                "qa_status": "VERIFIED",
                "gold": self.artifact("gold.json", self.gold),
                "evidence": self.artifact("ocr.json", self.source),
            }
        ]

    def run_manifest(self):
        path = self.base / "manifest.json"
        path.write_text(json.dumps(self.manifest))
        return evaluate(path)

    def assert_waiting(self, report):
        self.assertEqual(report["status"], "WAITING_FOR_VERIFIED_V2_GOLD", report)
        self.assertIsNone(report["metrics"])
        self.assertIsNone(report["modes"])
        self.assertIsNone(report["propagation_gap"])
        self.assertEqual(report["evaluated"], 0)
        self.assertTrue(report["reasons"])

    def test_absent_gold_fail_closed(self):
        self.assert_waiting(evaluate(self.base / "absent.json"))

    def test_empty_unverified_unfrozen_and_wrong_config(self):
        self.prepare()
        original = copy.deepcopy(self.manifest)
        for key, value in [
            ("records", []),
            ("frozen", False),
            ("qa_status", "DRAFT"),
            ("sample_count", 2),
            ("configuration", {}),
            ("verified_by", ""),
        ]:
            self.manifest = copy.deepcopy(original)
            self.manifest[key] = value
            with self.subTest(key=key):
                self.assert_waiting(self.run_manifest())

    def test_hash_mismatch(self):
        self.prepare()
        self.manifest["records"][0]["gold"]["sha256"] = "0" * 64
        self.assert_waiting(self.run_manifest())

    def test_bad_gold_schema(self):
        self.gold["annotation_schema_version"] = "1.3"
        self.prepare()
        self.assert_waiting(self.run_manifest())

    def test_bad_gold_type_and_nonfinite_values(self):
        for value in (True, "100000", float("inf")):
            self.gold["fields"]["subtotal"]["normalized_value"] = value
            self.prepare()
            with self.subTest(value=value):
                self.assert_waiting(self.run_manifest())

    def test_gold_money_accepts_currency_precision(self):
        for currency, values in (
            ("VND", (0, 123)),
            ("USD", (0, 123, 123.0, 123.4, 123.45, 0.01)),
        ):
            for value in values:
                gold = gold_fixture()
                gold["fields"]["currency"]["normalized_value"] = currency
                for field in ("subtotal", "tax_amount", "total_amount"):
                    gold["fields"][field]["normalized_value"] = value
                for field in ("unit_price", "amount"):
                    gold["line_items"][0][field]["normalized_value"] = value
                # Quantity has its own decimal policy, independent of money scale.
                gold["line_items"][0]["quantity"]["normalized_value"] = 1.5
                with self.subTest(currency=currency, value=value):
                    validate_gold(gold, self.source, self.manifest)

    def test_gold_money_rejects_excess_currency_precision(self):
        for currency, value in (
            ("VND", 123.0),
            ("VND", 123.45),
            ("VND", 0.01),
            ("USD", 123.456),
            ("USD", 0.001),
            ("USD", 123.45000000000002),
        ):
            for field in (
                "subtotal",
                "tax_amount",
                "total_amount",
                "unit_price",
                "amount",
            ):
                gold = gold_fixture()
                gold["fields"]["currency"]["normalized_value"] = currency
                cells = (
                    gold["fields"] if field in HEADER_FIELDS else gold["line_items"][0]
                )
                cells[field]["normalized_value"] = value
                with (
                    self.subTest(currency=currency, field=field, value=value),
                    self.assertRaises(ValueError),
                ):
                    validate_gold(gold, self.source, self.manifest)

    def test_gold_money_rejects_invalid_numeric_values(self):
        for currency in ("VND", "USD"):
            for field in ("subtotal", "amount"):
                for value in (
                    True,
                    False,
                    "123.45",
                    Decimal("123.45"),
                    -1,
                    -0.01,
                    float("inf"),
                    float("-inf"),
                    float("nan"),
                ):
                    gold = gold_fixture()
                    gold["fields"]["currency"]["normalized_value"] = currency
                    cells = (
                        gold["fields"]
                        if field in HEADER_FIELDS
                        else gold["line_items"][0]
                    )
                    cells[field]["normalized_value"] = value
                    with (
                        self.subTest(currency=currency, field=field, value=value),
                        self.assertRaises((ValueError, ValidationError)),
                    ):
                        validate_gold(gold, self.source, self.manifest)

    def test_usd_gold_evaluation_accepts_cents(self):
        self.source = invoice(rows=[["Dịch vụ mẫu", "gói", "1", "123.45", "123.45"]])
        for index, text in (
            (9, "Đơn vị tiền tệ: USD"),
            (20, "Cộng tiền hàng: 123.45"),
            (21, "Tổng tiền thuế: 0"),
            (22, "Tổng cộng: 123.45"),
        ):
            self.source["blocks"][index]["text"] = text
        for field, value in (
            ("currency", "USD"),
            ("subtotal", 123.45),
            ("tax_amount", 0),
            ("total_amount", 123.45),
        ):
            self.gold["fields"][field]["normalized_value"] = value
            self.gold["fields"][field]["raw_value"] = str(value)
        for field, value in (
            ("quantity", 1),
            ("unit_price", 123.45),
            ("amount", 123.45),
        ):
            self.gold["line_items"][0][field]["normalized_value"] = value
            self.gold["line_items"][0][field]["raw_value"] = str(value)
        self.prepare()
        report = self.run_manifest()
        self.assertEqual(report["status"], "COMPLETED", report)
        self.assertEqual(report["metrics"]["complete_invoice_accuracy"], 1)

    def test_malformed_freeze_provenance(self):
        self.prepare()
        for value in (None, "yesterday", "2026-09-29T00:00:00"):
            self.manifest["frozen_at"] = value
            with self.subTest(value=value):
                self.assert_waiting(self.run_manifest())

    def test_bad_gold_evidence_or_missing_header(self):
        self.gold["fields"]["invoice_number"]["source_block_ids"] = ["outside"]
        self.prepare()
        self.assert_waiting(self.run_manifest())
        del self.gold["fields"]["invoice_number"]
        self.prepare()
        self.assert_waiting(self.run_manifest())

    def test_duplicate_receipts(self):
        self.prepare()
        self.manifest["records"] *= 2
        self.manifest["sample_count"] = 2
        self.assert_waiting(self.run_manifest())

    def test_synthetic_evaluation_labels_and_provenance(self):
        self.prepare()
        report = self.run_manifest()
        self.assertEqual(report["status"], "COMPLETED", report)
        self.assertEqual(report["result_scope"], "synthetic_diagnostic")
        self.assertEqual(report["metrics"]["complete_invoice_accuracy"], 1)
        self.assertEqual(len(report["metrics"]["headers"]), 13)
        self.assertEqual(len(report["git_commit"]), 40)
        self.assertEqual(len(report["manifest_sha256"]), 64)
        self.assertIsNone(report["modes"]["oracle"])

    def test_metrics_wrong_values_miss_and_extra_rows(self):
        result = extract_invoice(self.source, kie_run_id=KIE_RUN)
        result["fields"]["invoice_number"]["normalized_value"] = "wrong"
        result["line_items"][0]["amount"]["normalized_value"] = 1
        extra = copy.deepcopy(result["line_items"][0])
        extra["source_block_ids"] = ["extra"]
        result["line_items"].append(extra)
        report = metrics([(result, self.gold)])
        self.assertEqual(report["headers"]["invoice_number"]["wrong"], 1)
        self.assertEqual(report["lines"]["detection_recall"], 1)
        self.assertEqual(report["lines"]["detection_precision"], 0.5)
        self.assertAlmostEqual(report["lines"]["detection_f1"], 2 / 3)
        self.assertEqual(report["lines"]["extra_row_rate"], 0.5)
        self.assertEqual(report["lines"]["matched_row_cell_correctness"], 0.8)
        self.assertEqual(report["lines"]["per_column_correctness"]["amount"], 0)
        self.assertEqual(report["lines"]["complete_line_accuracy"], 0)
        result["line_items"] = []
        report = metrics([(result, self.gold)])
        self.assertEqual(report["lines"]["detection_recall"], 0)
        self.assertEqual(report["lines"]["detection_f1"], 0)
        self.assertIsNone(report["lines"]["detection_precision"])
        self.assertIsNone(report["lines"]["matched_row_cell_correctness"])

    def test_missing_field_false_positive(self):
        result = extract_invoice(self.source, kie_run_id=KIE_RUN)
        self.gold["fields"]["buyer_name"].update(
            annotation_status="NOT_PRESENT", normalized_value=None
        )
        report = metrics([(result, self.gold)])
        self.assertEqual(report["headers"]["buyer_name"]["false_value"], 1)
        self.assertEqual(report["headers"]["buyer_name"]["exact_match"], 0)

    def test_one_to_one_matching_does_not_use_cell_values(self):
        result = extract_invoice(self.source, kie_run_id=KIE_RUN)
        row = result["line_items"][0]
        self.assertEqual(len(row_matches([row, row], self.gold["line_items"])), 1)
        self.assertEqual(
            row_matches(
                [{**row, "source_block_ids": ["unrelated"]}], self.gold["line_items"]
            ),
            [],
        )

    def test_verified_oracle_gap(self):
        oracle = copy.deepcopy(self.source)
        self.source["blocks"][2]["text"] = "Số hóa đơn: 00??049"
        self.prepare()
        self.manifest["records"][0].update(
            oracle_evidence=self.artifact("oracle.json", oracle),
            oracle_qa_status="VERIFIED",
        )
        report = self.run_manifest()
        self.assertEqual(report["status"], "COMPLETED", report)
        self.assertEqual(report["propagation_gap"]["invoice_number"], 1)
        self.assertEqual(report["metrics"]["error_taxonomy"]["OCR_PROPAGATION"], 1)

    def test_oracle_requires_verified_geometry(self):
        oracle = copy.deepcopy(self.source)
        oracle["blocks"][2]["polygon"][0]["x"] += 0.01
        self.prepare()
        self.manifest["records"][0].update(
            oracle_evidence=self.artifact("oracle.json", oracle),
            oracle_qa_status="VERIFIED",
        )
        self.assert_waiting(self.run_manifest())

    def test_zero_denominators_and_empty_table(self):
        report = metrics([])
        self.assertIsNone(report["lines"]["detection_f1"])
        self.assertIsNone(report["complete_invoice_accuracy"])
        self.assertIsNone(report["header_micro_accuracy"])
        result = extract_invoice(self.source, kie_run_id=KIE_RUN)
        result["line_items"] = []
        self.gold["line_items"] = []
        report = metrics([(result, self.gold)])
        for key in (
            "detection_precision",
            "detection_recall",
            "detection_f1",
            "extra_row_rate",
            "complete_line_accuracy",
        ):
            self.assertIsNone(report["lines"][key], key)
        self.assertEqual(report["complete_table_accuracy"], 1)
        self.assertEqual(report["complete_invoice_accuracy"], 1)
        result["line_items"] = extract_invoice(self.source, kie_run_id=KIE_RUN)[
            "line_items"
        ]
        report = metrics([(result, self.gold)])
        self.assertEqual(report["lines"]["detection_f1"], 0)
        self.assertEqual(report["lines"]["extra_row_rate"], 1)
        self.assertIsNone(report["lines"]["detection_recall"])

    def test_split_merge_and_shared_evidence(self):
        result = extract_invoice(self.source, kie_run_id=KIE_RUN)
        row = result["line_items"][0]
        result["line_items"] = [copy.deepcopy(row), copy.deepcopy(row)]
        split = metrics([(result, self.gold)])["lines"]
        self.assertEqual(split["matched_rows"], 1)
        self.assertEqual(split["detection_precision"], 0.5)
        self.assertAlmostEqual(split["detection_f1"], 2 / 3)
        self.gold["line_items"].append(copy.deepcopy(self.gold["line_items"][0]))
        self.gold["line_items"][1]["line_id"] = "gold-B"
        result["line_items"] = [row]
        merged = metrics([(result, self.gold)])["lines"]
        self.assertEqual(merged["detection_recall"], 0.5)
        self.assertEqual(merged["detection_precision"], 1)
        self.assertAlmostEqual(merged["detection_f1"], 2 / 3)
        # Shared evidence can saturate detection while all content is wrong.
        result["line_items"] = [copy.deepcopy(row), copy.deepcopy(row)]
        for item in result["line_items"]:
            item["description"]["normalized_value"] = "wrong"
        shared = metrics([(result, self.gold)])["lines"]
        self.assertEqual(shared["detection_f1"], 1)
        self.assertEqual(shared["complete_line_accuracy"], 0)

    def test_matching_reordering_and_augmenting_path(self):
        gold = [copy.deepcopy(self.gold["line_items"][0]) for _ in range(2)]
        for i, row in enumerate(gold):
            for f in LINE_FIELDS:
                row[f]["source_block_ids"] = [str(i)]
        predictions = [{"source_block_ids": ["0", "1"]}, {"source_block_ids": ["0"]}]
        self.assertEqual(row_matches(predictions, gold), [(0, 1), (1, 0)])
        self.assertEqual(
            row_matches(list(reversed(predictions)), gold), [(0, 0), (1, 1)]
        )
        self.assertEqual(
            row_matches(predictions, list(reversed(gold))), [(0, 0), (1, 1)]
        )

    def test_statuses_are_distinct_and_tax_is_not_scored(self):
        result = extract_invoice(self.source, kie_run_id=KIE_RUN)
        for status in ("UNKNOWN", "NOT_PRESENT", "UNREADABLE", "AMBIGUOUS"):
            self.gold["fields"]["buyer_name"].update(
                annotation_status=status, normalized_value=None
            )
            for predicted in ("UNKNOWN", "NOT_PRESENT", "UNREADABLE", "AMBIGUOUS"):
                result["fields"]["buyer_name"].update(
                    value_status=predicted, normalized_value=None
                )
                report = metrics([(result, self.gold)])
                self.assertEqual(
                    report["headers"]["buyer_name"]["exact_match"],
                    None if status == "UNKNOWN" else int(status == predicted),
                )
        before = metrics([(result, self.gold)])
        result["tax_breakdown"] = [{"deliberately": "not scored by this metric"}]
        self.assertEqual(before, metrics([(result, self.gold)]))
        self.assertIn("tax_breakdown_not_scored", before["scope"])

    def test_missing_gold_evidence_is_not_absence(self):
        self.gold["line_items"][0]["description"]["source_block_ids"] = []
        self.prepare()
        self.assert_waiting(self.run_manifest())
        for f in LINE_FIELDS:
            self.gold["line_items"][0][f].update(
                annotation_status="UNKNOWN", normalized_value=None, source_block_ids=[]
            )
        self.prepare()
        report = self.run_manifest()
        self.assert_waiting(report)
        self.assertEqual(report["coverage"]["required"], 1)
        self.assertEqual(len(report["failures"]), 1)
        self.assertIn("needs evidence", report["failures"][0]["reason"])

    def authorize_ab(self):
        self.manifest["experiment"] = {
            "protocol": "grouping-ab-1.0",
            "evaluator_version": VERSION,
            "configurations": copy.deepcopy(GROUPING_CONFIGURATIONS),
        }

    def run_ab(self):
        path = self.base / "manifest.json"
        path.write_text(json.dumps(self.manifest))
        return evaluate(path, comparison=True)

    def test_ab_requires_explicit_exact_configs_and_blocks_final_test(self):
        self.prepare()
        self.assert_waiting(self.run_ab())
        self.authorize_ab()
        original = copy.deepcopy(self.manifest)
        self.manifest["experiment"]["configurations"][INTERVAL_GROUPING]["version"] = (
            "other"
        )
        self.assert_waiting(self.run_ab())
        self.manifest = original
        path = self.base / "manifest.json"
        path.write_text(json.dumps(self.manifest))
        self.assert_waiting(evaluate(path, comparison=True, grouping=INTERVAL_GROUPING))
        self.manifest["split"] = "test"
        with patch("ai.kie.v2.evaluation.load_artifact") as load:
            self.assert_waiting(self.run_ab())
            load.assert_not_called()

    def test_ab_same_inputs_gold_matching_and_normalization(self):
        self.prepare()
        self.authorize_ab()
        report = self.run_ab()
        self.assertEqual(report["status"], "COMPLETED", report)
        self.assertEqual(report["coverage"]["fraction"], 1)
        self.assertEqual(report["delta"]["lines"]["detection_f1"], 0)
        sample = report["samples"][0]
        self.assertEqual(sample["gold"], self.gold)
        left, right = [
            sample["variants"][name]["real"]
            for name in (BASELINE_GROUPING, INTERVAL_GROUPING)
        ]
        self.assertEqual(left["row_matches"], right["row_matches"])
        a, b = left["prediction"], right["prediction"]
        self.assertEqual(a["kie_run_id"], b["kie_run_id"])
        self.assertEqual(a["fields"], b["fields"])
        self.assertEqual(a["line_items"], b["line_items"])
        self.assertEqual(
            left["normalization_ablation"]["status"], "NOT_RUN_QA_RAW_GOLD_REQUIRED"
        )

    def test_failed_variant_withholds_all_scores(self):
        self.prepare()
        self.authorize_ab()
        with patch(
            "ai.kie.v2.evaluation.extract_with_grouping",
            side_effect=RuntimeError("provider failure"),
        ):
            report = self.run_ab()
        self.assert_waiting(report)
        self.assertIsNone(report["variants"])
        self.assertIsNone(report["delta"])
        self.assertEqual(report["coverage"]["eligible"], 1)
        self.assertEqual(report["coverage"]["processed"], 0)
        self.assertNotIn(
            "metrics", report["samples"][0]["variants"][BASELINE_GROUPING]["real"]
        )
        self.assertEqual(report["failures"][0]["stage"], "extraction")

    def test_all_bad_records_are_reported_no_partial_evaluation(self):
        self.prepare()
        self.manifest["records"][0]["gold"]["sha256"] = "0" * 64
        self.manifest["records"].append({"qa_status": "DRAFT"})
        self.manifest["sample_count"] = 2
        with patch("ai.kie.v2.evaluation.extract_invoice") as extractor:
            report = self.run_manifest()
            extractor.assert_not_called()
        self.assert_waiting(report)
        self.assertEqual(len(report["failures"]), 2)
        self.assertEqual(report["coverage"]["required"], 2)
        self.assertEqual(report["coverage"]["fraction"], 0)

    def test_normalization_ablation_requires_compatible_printed_gold(self):
        self.manifest["raw_value_protocol"] = "selected-value-text-v1"
        self.gold["fields"]["invoice_date"]["raw_value"] = "19/09/2026"
        self.gold["fields"]["seller_tax_id"]["raw_value"] = "0101 234 567"
        self.prepare()
        report = self.run_manifest()
        ablation = report["samples"][0]["variants"][BASELINE_GROUPING]["real"][
            "normalization_ablation"
        ]
        self.assertEqual(ablation["metrics"]["predicted_exact_match"], 1)
        self.assertEqual(ablation["metrics"]["normalized_exact_match"], 1)
        self.gold["fields"]["subtotal"]["raw_value"] = 100000
        self.prepare()
        self.assert_waiting(self.run_manifest())

    def test_oracle_confidence_cannot_change_as_text_ablation(self):
        self.prepare()
        oracle = copy.deepcopy(self.source)
        oracle["blocks"][2]["confidence"] = 0.1
        self.manifest["records"][0].update(
            oracle_evidence=self.artifact("oracle.json", oracle),
            oracle_qa_status="VERIFIED",
        )
        self.assert_waiting(self.run_manifest())

    def test_ab_synthetic_column_failure_and_csv_exports(self):
        self.source = narrow_numbers()
        self.gold["fields"] = {
            f: {
                "annotation_status": "UNKNOWN",
                "normalized_value": None,
                "raw_value": None,
                "source_block_ids": [],
            }
            for f in HEADER_FIELDS
        }
        self.gold["fields"]["currency"] = {
            "annotation_status": "PRESENT",
            "normalized_value": "VND",
            "raw_value": "VND",
            "source_block_ids": ["p0_b0"],
        }
        for f, v, i in zip(
            LINE_FIELDS, ["Service A", "box", 2, 50000, 100000], range(6, 11)
        ):
            self.gold["line_items"][0][f] = {
                "annotation_status": "PRESENT",
                "normalized_value": v,
                "raw_value": str(v),
                "source_block_ids": [f"p0_b{i}"],
            }
        self.prepare()
        self.authorize_ab()
        report = self.run_ab()
        self.assertEqual(report["status"], "COMPLETED", report)
        left, right = [
            report["variants"][name]["metrics"]["lines"]
            for name in (BASELINE_GROUPING, INTERVAL_GROUPING)
        ]
        self.assertEqual(left["matched_row_cell_correctness"], 0.6)
        self.assertEqual(right["matched_row_cell_correctness"], 1)
        self.assertEqual(left["detection_f1"], right["detection_f1"])
        self.assertEqual(report["delta"]["lines"]["complete_line_accuracy"], 1)
        command = [
            sys.executable,
            "scripts/evaluate_invoice_kie.py",
            "--manifest",
            str(self.base / "manifest.json"),
            "--compare",
            "--output",
            str(self.base / "run"),
        ]
        process = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(
            json.loads((self.base / "run/report.json").read_text())["evaluated"], 1
        )
        with (self.base / "run/summary.csv").open() as handle:
            summary = {r["metric"]: r for r in csv.DictReader(handle)}
        self.assertEqual(
            float(summary["lines.matched_row_cell_correctness"]["delta"]), 0.4
        )
        with (self.base / "run/samples.csv").open() as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 2)
        # Never overwrite a previous run, even when the new result might differ.
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)

    def test_currency_precision_matches_v2_money_contract(self):
        for currency, amount, allowed in [
            ("USD", 10.25, True),
            ("USD", 10.255, False),
            ("VND", 10.25, False),
        ]:
            with self.subTest(currency=currency, amount=amount):
                self.gold["fields"]["currency"]["normalized_value"] = currency
                self.gold["fields"]["subtotal"]["normalized_value"] = amount
                self.prepare()
                report = self.run_manifest()
                if allowed:
                    self.assertEqual(report["status"], "COMPLETED", report)
                else:
                    self.assert_waiting(report)


if __name__ == "__main__":
    unittest.main()
