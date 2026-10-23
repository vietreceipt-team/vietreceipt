"""Evaluator protocol tests with synthetic, temporary gold; not thesis evaluation."""

import copy
import hashlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from jsonschema import ValidationError

from ai.kie.v2 import extract_invoice
from ai.kie.v2.config import CONFIGURATION, HEADER_FIELDS, LINE_FIELDS
from ai.kie.v2.evaluation import evaluate, metrics, row_matches, validate_gold
from tests.kie_v2_fixtures import KIE_RUN, RECEIPT, invoice


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
            for field in ("subtotal", "tax_amount", "total_amount", "unit_price", "amount"):
                gold = gold_fixture()
                gold["fields"]["currency"]["normalized_value"] = currency
                cells = gold["fields"] if field in HEADER_FIELDS else gold["line_items"][0]
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
                    cells = gold["fields"] if field in HEADER_FIELDS else gold["line_items"][0]
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
        for field, value in (("quantity", 1), ("unit_price", 123.45), ("amount", 123.45)):
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
        self.assertEqual(report["lines"]["extra_row_rate"], 0.5)
        self.assertEqual(report["lines"]["matched_row_cell_correctness"], 0.8)
        self.assertEqual(report["lines"]["per_column_correctness"]["amount"], 0)
        self.assertEqual(report["lines"]["complete_line_accuracy"], 0)
        result["line_items"] = []
        report = metrics([(result, self.gold)])
        self.assertEqual(report["lines"]["detection_recall"], 0)
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


if __name__ == "__main__":
    unittest.main()
