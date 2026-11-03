"""Table/Layout handoff regressions; synthetic fixtures, not accuracy results."""

import copy
import unittest

from ai.kie.v2 import extract_invoice, extract_with_grouping
from ai.kie.v2.config import INTERVAL_GROUPING
from ai.kie.v2.contract import validate_result
from ai.kie.v2.evidence import flatten
from ai.table import extract_table
from tests.kie_v2_fixtures import KIE_RUN, document, evidence, invoice
from tests.kie_v2_grouping_fixtures import narrow_numbers


class TableRegionTests(unittest.TestCase):
    def extract(self, source=None, **kwargs):
        options = {"page_index": 0, "bbox": (0, 0.33, 1, 0.65), "currency": "VND"}
        options.update(kwargs)
        return extract_table(invoice() if source is None else source, **options)

    def test_region_matches_existing_rows_and_preserves_original_evidence(self):
        source = invoice()
        original = copy.deepcopy(source)
        table = self.extract(source)
        result = extract_invoice(source, kie_run_id=KIE_RUN)
        self.assertEqual(table["line_items"], result["line_items"])
        result["line_items"] = table["line_items"]
        validate_result(result, source, kie_run_id=KIE_RUN)
        self.assertEqual(table["status"], "EXTRACTED")
        self.assertEqual(table["receipt_id"], source["receipt_id"])
        self.assertEqual(table["source_ocr_run_id"], source["ocr_run_id"])
        self.assertEqual(source, original)
        self.assertEqual(table, self.extract(source))
        ids = set(table["source_block_ids"])
        self.assertTrue(set(table["line_items"][0]["source_block_ids"]) <= ids)
        self.assertTrue(
            all(
                0.33 <= b["polygon"][0]["y"] < 0.65
                for b in source["blocks"]
                if b["block_id"] in ids
            )
        )

    def test_document_selects_only_requested_page(self):
        first = invoice()
        second = evidence(
            [
                (
                    b["text"],
                    b["polygon"][0]["x"],
                    b["polygon"][0]["y"],
                    b["polygon"][1]["x"] - b["polygon"][0]["x"],
                )
                for b in first["blocks"]
            ],
            prefix="p1",
        )
        table = self.extract(document(first, second), page_index=1)
        self.assertEqual(len(table["line_items"]), 1)
        self.assertTrue(all(i.startswith("p1_") for i in table["source_block_ids"]))
        blocks = {b.block_id: b for b in flatten(document(first, second))}
        for block_id in table["line_items"][0]["description"]["source_block_ids"]:
            self.assertEqual(blocks[block_id].page, 1)
            self.assertEqual(blocks[block_id].top, 0.38)

    def test_empty_and_unheaded_regions_are_explicit(self):
        for source in (evidence([]), evidence([("An item", 0.1, 0.4)])):
            table = self.extract(source)
            self.assertEqual(table["status"], "NO_ROWS_DETECTED")
            self.assertEqual(table["line_items"], [])

    def test_region_cannot_silently_cut_an_ocr_block(self):
        with self.assertRaisesRegex(ValueError, "boundary crosses source block"):
            self.extract(bbox=(0.1, 0.33, 1, 0.65))

    def test_touching_block_boundary_is_not_an_intersection(self):
        source = evidence([("Outside", 0.0, 0.4, 0.1)])
        table = self.extract(source, bbox=(0.1, 0.33, 1, 0.65))
        self.assertEqual(table["source_block_ids"], [])

    def test_full_page_does_not_turn_totals_or_tax_rows_into_line_items(self):
        source = invoice(tax_groups=True)
        table = self.extract(source, bbox=(0, 0, 1, 1))
        self.assertEqual(len(table["line_items"]), 1)
        self.assertEqual(
            table["line_items"],
            extract_invoice(source, kie_run_id=KIE_RUN)["line_items"],
        )

    def test_invalid_evidence_outside_the_region_is_still_rejected(self):
        source = invoice()
        source["blocks"][0]["polygon"][0]["x"] = float("nan")
        with self.assertRaises(ValueError):
            self.extract(source)

    def test_invalid_region_page_and_grouping(self):
        for bbox in (
            None,
            (),
            (0, 0, 1),
            (0, 0, 1, float("nan")),
            (0, 0, 1, float("inf")),
            (-0.1, 0, 1, 1),
            (0, 0, 1.1, 1),
            (0.5, 0, 0.5, 1),
            (0, 0.8, 1, 0.2),
            (False, 0, 1, 1),
        ):
            with self.subTest(bbox=bbox), self.assertRaises(ValueError):
                self.extract(bbox=bbox)
        for page in (-1, True, 0.5, 1):
            with self.subTest(page=page), self.assertRaises(ValueError):
                self.extract(page_index=page)
        with self.assertRaises(ValueError):
            self.extract(grouping="unknown")

    def test_missing_currency_keeps_monetary_uncertainty(self):
        row = self.extract(currency=None)["line_items"][0]
        self.assertIsNone(row["amount"]["normalized_value"])
        self.assertTrue(row["amount"]["machine_needs_review"])
        row = self.extract(currency="EUR")["line_items"][0]
        self.assertIn("UNSUPPORTED_CURRENCY", row["amount"]["review_reasons"])

    def test_interval_experiment_is_explicit_and_matches_existing_variant(self):
        source = narrow_numbers()
        table = self.extract(source, bbox=(0, 0, 1, 1), grouping=INTERVAL_GROUPING)
        result = extract_with_grouping(
            source, kie_run_id=KIE_RUN, grouping=INTERVAL_GROUPING
        )
        self.assertEqual(table["line_items"], result["line_items"])
        self.assertEqual(table["configuration"], result["configuration"])


if __name__ == "__main__":
    unittest.main()
