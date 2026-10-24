"""Independent synthetic source-region protocol tests; never dataset QA."""

import copy
import unittest

from jsonschema import ValidationError

from ai.kie.v2 import extract_invoice
from ai.kie.v2.config import LINE_FIELDS
from ai.kie.v2.evaluation import metrics, validate_gold
from ai.kie.v2.source_evaluation import (
    source_metrics,
    spatial_matches,
    validate_regions,
)
from tests.kie_v2_fixtures import KIE_RUN, evidence, invoice
from tests.test_kie_v2_evaluation import gold_fixture


class SourceEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.evidence = invoice()
        self.gold = gold_fixture()
        for cell in list(self.gold["fields"].values()) + [
            self.gold["line_items"][0][f] for f in LINE_FIELDS
        ]:
            cell["source_block_ids"] = []
        self.regions = [
            {"line_id": "gold-A", "page_index": 0, "bounds": [0.05, 0.38, 0.97, 0.394]}
        ]
        self.result = extract_invoice(self.evidence, kie_run_id=KIE_RUN)

    def case(self, result):
        return result, self.gold, self.evidence, self.regions

    def match_boxes(self, predicted, gold, *, gold_pages=None):
        source = evidence(
            [
                (f"row-{i}", box[0], box[1], box[2] - box[0])
                for i, box in enumerate(predicted)
            ]
        )
        for block, box in zip(source["blocks"], predicted):
            block["polygon"] = [
                {"x": box[0], "y": box[1]},
                {"x": box[2], "y": box[1]},
                {"x": box[2], "y": box[3]},
                {"x": box[0], "y": box[3]},
            ]
        rows = [{"source_block_ids": [f"p0_b{i}"]} for i in range(len(predicted))]
        target = copy.deepcopy(self.gold)
        target["line_items"] = [copy.deepcopy(self.gold["line_items"][0]) for _ in gold]
        for i, row in enumerate(target["line_items"]):
            row["line_id"] = f"gold-{i}"
        pages = gold_pages or [0] * len(gold)
        regions = [
            {"line_id": f"gold-{i}", "page_index": pages[i], "bounds": box}
            for i, box in enumerate(gold)
        ]
        matches = spatial_matches(rows, source, target, regions)
        return matches, (
            len(matches),
            len(predicted) - len(matches),
            len(gold) - len(matches),
        )

    def test_source_matching_needs_no_gold_ocr_ids(self):
        report = source_metrics([self.case(self.result)])
        self.assertEqual(report["lines"]["detection_f1"], 1)
        self.assertEqual(report["complete_invoice_accuracy"], 1)

    def test_ocr_missing_row_stays_in_denominator(self):
        self.evidence["blocks"] = (
            self.evidence["blocks"][:15] + self.evidence["blocks"][20:]
        )
        for i, block in enumerate(self.evidence["blocks"]):
            block["reading_order"] = i
        result = extract_invoice(self.evidence, kie_run_id=KIE_RUN)
        report = source_metrics([self.case(result)])
        self.assertEqual(report["lines"]["gold_rows"], 1)
        self.assertEqual(report["lines"]["detection_recall"], 0)
        self.assertEqual(report["complete_invoice_accuracy"], 0)

    def test_reader_failure_kept_with_known_gold(self):
        report = source_metrics(
            [self.case(self.result), (None, self.gold, None, self.regions)]
        )
        self.assertEqual(report["lines"]["documents"], 2)
        self.assertEqual(report["lines"]["failed_documents"], 1)
        for key in (
            "complete_header_accuracy",
            "complete_table_accuracy",
            "complete_invoice_accuracy",
        ):
            self.assertEqual(report[key], 0.5)
        self.assertEqual(report["lines"]["detection_recall"], 0.5)
        self.assertEqual(report["headers"]["invoice_number"]["miss"], 1)

    def test_failed_empty_table_is_not_complete(self):
        self.gold["line_items"] = []
        report = source_metrics([(None, self.gold, None, [])])
        self.assertEqual(report["complete_table_accuracy"], 0)
        self.assertIsNone(report["lines"]["detection_f1"])

    def test_split_merge_and_values_cannot_increase_matches(self):
        rows = self.result["line_items"]
        match = spatial_matches(rows, self.evidence, self.gold, self.regions)
        self.assertEqual(
            len(spatial_matches(rows * 2, self.evidence, self.gold, self.regions)), 1
        )
        self.gold["line_items"].append(copy.deepcopy(self.gold["line_items"][0]))
        self.gold["line_items"][1]["line_id"] = "gold-B"
        self.regions.append({**self.regions[0], "line_id": "gold-B"})
        self.assertEqual(
            len(spatial_matches(rows, self.evidence, self.gold, self.regions)), 1
        )
        self.gold["line_items"].pop()
        self.regions.pop()
        rows[0]["amount"]["normalized_value"] = 999999
        self.assertEqual(
            spatial_matches(rows, self.evidence, self.gold, self.regions), match
        )
        self.regions[0]["page_index"] = 1
        self.assertEqual(
            spatial_matches(rows, self.evidence, self.gold, self.regions), []
        )

    def test_source_matcher_stress_matrix(self):
        """TV1 R01-R05/R07: overlap boundary and cardinality evidence."""
        left = [0.10, 0.20, 0.50, 0.30]
        edge_touch = [0.50, 0.20, 0.90, 0.30]
        tiny_overlap = [0.499999, 0.20, 0.90, 0.30]

        self.assertEqual(self.match_boxes([left], [edge_touch]), ([], (0, 1, 1)))
        self.assertEqual(
            self.match_boxes([left], [tiny_overlap]), ([(0, 0)], (1, 0, 0))
        )
        self.assertEqual(
            self.match_boxes(
                [[0.10, 0.20, 0.90, 0.25], [0.10, 0.30, 0.90, 0.35]],
                [[0.10, 0.20, 0.90, 0.25], [0.10, 0.30, 0.90, 0.35]],
            )[1],
            (2, 0, 0),
        )
        self.assertEqual(
            self.match_boxes(
                [[0.10, 0.20, 0.90, 0.40]],
                [[0.10, 0.20, 0.90, 0.29], [0.10, 0.31, 0.90, 0.40]],
            )[1],
            (1, 0, 1),
        )
        self.assertEqual(
            self.match_boxes(
                [[0.10, 0.20, 0.90, 0.29], [0.10, 0.31, 0.90, 0.40]],
                [[0.10, 0.20, 0.90, 0.40]],
            )[1],
            (1, 1, 0),
        )
        same = [[0.10, 0.20, 0.90, 0.30], [0.10, 0.20, 0.90, 0.30]]
        first = self.match_boxes(same, same)[0]
        self.assertEqual(first, self.match_boxes(same, same)[0])
        self.assertEqual(first, [(0, 1), (1, 0)])
        self.assertEqual(
            self.match_boxes([left], [left], gold_pages=[1]), ([], (0, 1, 1))
        )
        self.assertEqual(
            self.match_boxes([[0.60, 0.60, 0.90, 0.70]], [left]),
            ([], (0, 1, 1)),
        )

    def test_invalid_regions_and_leaked_gold_ids_rejected(self):
        for bounds in ([0, 0, 0, 1], [0, 0, float("nan"), 1], [-0.1, 0, 1, 1]):
            with self.assertRaises(ValueError):
                validate_regions([{**self.regions[0], "bounds": bounds}], self.gold)
        self.gold["fields"]["invoice_number"]["source_block_ids"] = ["p0_b2"]
        with self.assertRaises(ValueError):
            source_metrics([self.case(self.result)])

    def test_unknown_mask_and_strict_denominators(self):
        gold = gold_fixture()
        gold["fields"]["buyer_name"].update(
            annotation_status="UNKNOWN", normalized_value=None
        )
        gold["line_items"][0]["unit"].update(
            annotation_status="UNKNOWN", normalized_value=None
        )
        report = metrics([(self.result, gold)])
        self.assertEqual(
            report["header_coverage"], {"eligible": 13, "scored": 12, "unknown": 1}
        )
        self.assertEqual(report["header_micro_accuracy"], 1)
        self.assertEqual(report["lines"]["matched_cells_scored"], 4)
        self.assertEqual(report["lines"]["matched_cells_unknown"], 1)
        self.assertEqual(report["lines"]["matched_row_cell_correctness"], 1)
        self.assertIsNone(report["lines"]["per_column_correctness"]["unit"])
        self.assertIsNone(report["lines"]["complete_line_accuracy"])
        self.assertIsNone(report["complete_header_accuracy"])
        self.assertIsNone(report["complete_table_accuracy"])
        self.assertIsNone(report["complete_invoice_accuracy"])

    def test_money_matches_upstream_precision_contract(self):
        for currency, amount, valid in [
            ("VND", 100000.0, False),
            ("VND", 100000, True),
            ("USD", 10.25, True),
            ("USD", 10.251, False),
            ("USD", float("inf"), False),
            ("USD", True, False),
        ]:
            with self.subTest(currency=currency, amount=amount):
                gold = copy.deepcopy(self.gold)
                gold["fields"]["currency"]["normalized_value"] = currency
                gold["fields"]["total_amount"]["normalized_value"] = amount
                if valid:
                    validate_gold(gold, None, gold, aligned=False)
                else:
                    with self.assertRaises(
                        (ValueError, ArithmeticError, ValidationError)
                    ):
                        validate_gold(gold, None, gold, aligned=False)
