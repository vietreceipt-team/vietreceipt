"""Synthetic regression and baseline invariance, not an accuracy benchmark."""

import copy
import hashlib
import json
import unittest
from pathlib import Path

from ai.kie.v2 import extract_invoice, extract_with_grouping
from ai.kie.v2.config import BASELINE_GROUPING, INTERVAL_GROUPING, LINE_FIELDS
from ai.kie.v2.consistency import check
from ai.kie.v2.evidence import flatten
from ai.kie.v2.extraction import group_columns
from ai.kie.v2.grouping import interval_columns
from tests.kie_v2_fixtures import KIE_RUN
from tests.kie_v2_grouping_fixtures import cases, narrow_numbers


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


class GroupingTests(unittest.TestCase):
    def variant(self, source):
        return extract_with_grouping(
            source, kie_run_id=KIE_RUN, grouping=INTERVAL_GROUPING
        )

    def test_baseline_is_byte_equivalent_to_pre_change_commit(self):
        snapshot = json.loads(
            (Path(__file__).parent / "fixtures/kie49/baseline-sha256.json").read_text()
        )
        self.assertEqual(set(snapshot["cases"]), set(cases()))
        for name, source in cases().items():
            with self.subTest(name=name):
                expected = snapshot["cases"][name]
                self.assertEqual(digest(source), expected["evidence_sha256"])
                result = extract_invoice(source, kie_run_id=KIE_RUN)
                self.assertEqual(digest(result), expected["result_sha256"])
                self.assertEqual(
                    result,
                    extract_with_grouping(
                        source, kie_run_id=KIE_RUN, grouping=BASELINE_GROUPING
                    ),
                )

    def test_narrow_right_aligned_numbers(self):
        source = narrow_numbers()
        original = copy.deepcopy(source)
        baseline, variant = (
            extract_invoice(source, kie_run_id=KIE_RUN),
            self.variant(source),
        )
        self.assertEqual(source, original)
        self.assertEqual(variant, self.variant(source))
        self.assertIsNone(baseline["line_items"][0]["quantity"]["normalized_value"])
        row = variant["line_items"][0]
        self.assertEqual(
            [row[f]["normalized_value"] for f in LINE_FIELDS],
            ["Service A", "box", 2, 50000, 100000],
        )
        self.assertEqual(row["quantity"]["raw_text"], "2")
        self.assertEqual(
            row["quantity"]["source_block_ids"], [source["blocks"][8]["block_id"]]
        )
        self.assertEqual(variant["fields"], baseline["fields"])
        self.assertEqual(variant["tax_breakdown"], baseline["tax_breakdown"])

    def test_other_geometry_cases_retain_baseline_behavior(self):
        for name, source in cases().items():
            if name == "narrow-right-aligned":
                continue
            with self.subTest(name=name):
                baseline = extract_invoice(source, kie_run_id=KIE_RUN)
                variant = self.variant(source)
                variant["configuration"] = baseline["configuration"]
                variant["extractor"] = baseline["extractor"]
                self.assertEqual(variant, baseline)

    def test_wrapped_and_split_description_preserve_evidence(self):
        for name, expected, block in [
            ("wrapped-description", "Dịch vụ mẫu continued name", "wrapped"),
            ("split-description", "Dịch vụ mẫu", "split"),
        ]:
            row = self.variant(cases()[name])["line_items"][0]
            self.assertEqual(row["description"]["normalized_value"], expected)
            self.assertIn(block, row["description"]["source_block_ids"])
        self.assertIn(
            "AMBIGUOUS_FORMAT",
            self.variant(cases()["wrapped-description"])["line_items"][0][
                "review_reasons"
            ],
        )

    def test_partial_rows_unit_absence_and_unsupported_layout(self):
        missing_column = self.variant(cases()["missing-unit-column"])["line_items"][0]
        missing_cell = self.variant(cases()["missing-unit-cell"])["line_items"][0]
        self.assertEqual(missing_column["unit"]["value_status"], "NOT_PRESENT")
        self.assertEqual(missing_cell["unit"]["value_status"], "UNKNOWN")
        self.assertEqual(
            len(self.variant(cases()["partial-next-item"])["line_items"]), 2
        )
        self.assertEqual(self.variant(cases()["unheaded"])["line_items"], [])

    def test_merged_block_is_not_split_into_invented_numbers(self):
        row = self.variant(cases()["merged-numeric-block"])["line_items"][0]
        self.assertEqual(row["unit_price"]["raw_text"], "50000 100000")
        self.assertIsNone(row["unit_price"]["normalized_value"])
        self.assertEqual(row["amount"]["value_status"], "UNKNOWN")

    def test_repeated_header_and_multiple_vat(self):
        rows = self.variant(cases()["repeated-header"])["line_items"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["description"]["normalized_value"], "Second page")
        self.assertTrue(all(i.startswith("p1_") for i in rows[1]["source_block_ids"]))
        taxes = self.variant(cases()["multiple-vat"])["tax_breakdown"]
        self.assertEqual([g["rate"]["normalized_value"] for g in taxes], ["5%", "8%"])
        self.assertEqual(
            [g["tax_amount"]["normalized_value"] for g in taxes], [5000, 16000]
        )

    def test_consistency_checks_do_not_change_values(self):
        result = self.variant(cases()["aligned"])
        result["line_items"][0]["amount"]["normalized_value"] = 123

        def values(r):
            return [
                (c["predicted_value"], c["normalized_value"], c["value_status"])
                for c in list(r["fields"].values())
                + [row[f] for row in r["line_items"] for f in LINE_FIELDS]
            ]

        before = values(result)
        check(result)
        self.assertEqual(before, values(result))
        self.assertEqual(result["consistency"]["checks"][0]["status"], "WARNING")

    def test_overlapping_header_intervals_fall_back(self):
        source = narrow_numbers()
        # Quantity block is now inside both quantity and price header spans.
        source["blocks"][4]["polygon"][0]["x"] = 0.50
        source["blocks"][4]["polygon"][3]["x"] = 0.50
        blocks = flatten(source)
        columns = dict(zip(LINE_FIELDS, blocks[1:6]))
        self.assertEqual(
            interval_columns([blocks[8]], columns), group_columns([blocks[8]], columns)
        )

    def test_close_partial_item_remains_known_continuation_limit(self):
        source = cases()["partial-next-item"]
        for block in source["blocks"]:
            if block["text"] == "B":
                for point in block["polygon"]:
                    point["y"] -= 0.02
        # B could be another product. Neither strategy claims to resolve this;
        # retain the source and review warning instead of reporting it as fixed.
        for result in (
            extract_invoice(source, kie_run_id=KIE_RUN),
            self.variant(source),
        ):
            self.assertEqual(len(result["line_items"]), 1)
            row = result["line_items"][0]
            self.assertEqual(row["description"]["normalized_value"], "A B")
            self.assertEqual(len(row["description"]["source_block_ids"]), 2)
            self.assertIn("AMBIGUOUS_FORMAT", row["review_reasons"])


if __name__ == "__main__":
    unittest.main()
