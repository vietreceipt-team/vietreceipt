"""Explicit Layout-to-invoice integration using synthetic source evidence."""

import copy
import unittest

from ai.kie.v2 import extract_invoice
from ai.kie.v2.config import BASELINE_GROUPING, INTERVAL_GROUPING
from ai.kie.v2.contract import validate_result
from ai.table import extract_invoice_with_tables
from tests.kie_v2_fixtures import KIE_RUN, document, evidence, invoice


def two_tables():
    source = invoice(total="216000")
    second = []
    for block in source["blocks"]:
        top = block["polygon"][0]["y"]
        if 0.33 <= top < 0.4:
            block = copy.deepcopy(block)
            block["block_id"] += "_second"
            for point in block["polygon"]:
                point["y"] += 0.2
            second.append(block)
    source["blocks"].extend(second)
    for i, block in enumerate(source["blocks"]):
        block["reading_order"] = i
        block["text"] = block["text"].replace(
            "Cộng tiền hàng: 100000", "Cộng tiền hàng: 200000"
        )
        block["text"] = block["text"].replace(
            "Tổng tiền thuế: 8000", "Tổng tiền thuế: 16000"
        )
    return source


class TablePipelineTests(unittest.TestCase):
    def extract(self, source=None, regions=None, **kwargs):
        return extract_invoice_with_tables(
            invoice() if source is None else source,
            kie_run_id=KIE_RUN,
            regions=regions
            if regions is not None
            else [{"page_index": 0, "bbox": [0, 0.33, 1, 0.65]}],
            **kwargs,
        )

    def test_one_table_is_canonical_and_preserves_baseline_cells(self):
        source = invoice()
        before = copy.deepcopy(source)
        result = self.extract(source)
        baseline = extract_invoice(source, kie_run_id=KIE_RUN)
        for key in ("fields", "line_items", "tax_breakdown", "consistency"):
            self.assertEqual(result[key], baseline[key])
        self.assertEqual(result["extractor"]["name"], "layout-region-invoice-kie")
        self.assertNotEqual(result["configuration"], baseline["configuration"])
        validate_result(result, source, kie_run_id=KIE_RUN)
        self.assertEqual(result, self.extract(source))
        self.assertEqual(source, before)

    def test_multiple_regions_are_ordered_and_checked_after_combining(self):
        source = two_tables()
        regions = [
            {"page_index": 0, "bbox": [0, 0.53, 1, 0.65]},
            {"page_index": 0, "bbox": [0, 0.33, 1, 0.45]},
        ]
        before = copy.deepcopy((source, regions))
        result = self.extract(source, regions)
        rows = result["line_items"]
        self.assertEqual([r["line_id"] for r in rows], ["line-0001", "line-0002"])
        self.assertTrue(all(i.endswith("_second") for i in rows[1]["source_block_ids"]))
        self.assertTrue(
            set(rows[0]["source_block_ids"]).isdisjoint(rows[1]["source_block_ids"])
        )
        self.assertEqual(result["consistency"]["checks"][0]["status"], "PASS")
        self.assertEqual(result["consistency"]["checks"][0]["difference_vnd"], 0)
        validate_result(result, source, kie_run_id=KIE_RUN)
        self.assertEqual((source, regions), before)

    def test_multiple_pages_do_not_share_ids_or_coordinates(self):
        first, second = invoice(), invoice()
        for block in second["blocks"]:
            block["block_id"] = block["block_id"].replace("p0_", "p1_")
        source = document(first, second)
        result = self.extract(
            source,
            [{"page_index": page, "bbox": [0, 0.33, 1, 0.65]} for page in (1, 0)],
        )
        self.assertEqual(len(result["line_items"]), 2)
        for page, row in enumerate(result["line_items"]):
            self.assertTrue(
                all(i.startswith(f"p{page}_") for i in row["source_block_ids"])
            )
        self.assertEqual(result["consistency"]["checks"][0]["status"], "WARNING")
        self.assertTrue(all(r["machine_needs_review"] for r in result["line_items"]))
        validate_result(result, source, kie_run_id=KIE_RUN)

    def test_overlapping_and_duplicate_regions_are_rejected(self):
        region = {"page_index": 0, "bbox": [0, 0.33, 1, 0.65]}
        for second in (region, {"page_index": 0, "bbox": [0, 0.32, 1, 0.66]}):
            with (
                self.subTest(second=second),
                self.assertRaisesRegex(ValueError, "overlap"),
            ):
                self.extract(regions=[region, second])

    def test_layout_table_evidence_is_not_used_as_header_currency(self):
        source = invoice()
        extra = evidence([("Currency: USD", 0.1, 0.6)])["blocks"][0]
        extra["block_id"] = "table_currency_note"
        extra["reading_order"] = len(source["blocks"])
        source["blocks"].append(extra)
        result = self.extract(source)
        self.assertEqual(result["fields"]["currency"]["normalized_value"], "VND")
        self.assertNotIn(
            extra["block_id"], result["fields"]["currency"]["source_block_ids"]
        )

    def test_empty_invalid_and_unheaded_regions_fail_explicitly(self):
        for regions in (
            None,
            [],
            {},
            [None],
            [{}],
            [{"page_index": 0, "bbox": [0, 0, 1, 1], "extra": True}],
        ):
            with self.subTest(regions=regions), self.assertRaises(ValueError):
                extract_invoice_with_tables(
                    invoice(), kie_run_id=KIE_RUN, regions=regions
                )
        with self.assertRaisesRegex(ValueError, "No table rows detected"):
            self.extract(evidence([("An item", 0.1, 0.4)]))
        with self.assertRaisesRegex(ValueError, "No table rows detected"):
            self.extract(
                regions=[
                    {"page_index": 0, "bbox": [0, 0.33, 1, 0.65]},
                    {"page_index": 0, "bbox": [0, 0.85, 1, 0.95]},
                ]
            )
        with self.assertRaises(ValueError):
            self.extract(regions=[{"page_index": 0, "bbox": [0.1, 0.33, 1, 0.65]}])

    def test_strategy_is_explicit_and_invalid_run_is_rejected(self):
        for grouping in (BASELINE_GROUPING, INTERVAL_GROUPING):
            result = self.extract(grouping=grouping)
            validate_result(result, invoice(), kie_run_id=KIE_RUN)
        with self.assertRaises(TypeError):
            extract_invoice_with_tables(
                invoice(),
                kie_run_id=str(KIE_RUN),
                regions=[{"page_index": 0, "bbox": [0, 0.33, 1, 0.65]}],
            )


if __name__ == "__main__":
    unittest.main()
