"""Synthetic characterization and layout diagnostics; not independent gold."""

import copy
import json
import unittest
from pathlib import Path

from ai.kie.v2 import extract_invoice, extract_with_layout
from ai.kie.v2.config import HEADER_FIELDS, LAYOUT_CONFIGURATION
from ai.kie.v2.evaluation import metrics
from ai.kie.v2.evidence import flatten
from ai.kie.v2.extraction import header_candidates, table_regions
from tests.kie_v2_fixtures import KIE_RUN, evidence


class HeaderBaselineCharacterization(unittest.TestCase):
    def test_table_cells_excluded_but_footer_totals_retained(self):
        source = evidence(
            [
                ("Currency: VND", 0.05, 0.04),
                ("Description", 0.05, 0.30),
                ("Quantity", 0.45, 0.30),
                ("Amount", 0.75, 0.30),
                ("Service", 0.05, 0.36),
                ("2", 0.45, 0.36),
                ("100", 0.75, 0.36),
                ("Subtotal: 100", 0.05, 0.72),
                ("Tax amount: 8", 0.05, 0.76),
                ("Total: 108", 0.05, 0.80),
            ]
        )
        blocks = flatten(source)
        _, excluded = table_regions(blocks)
        candidates = header_candidates(blocks, excluded)
        self.assertIn("p0_b4", excluded)
        self.assertEqual([c.value for c in candidates["total_amount"]], ["108"])
        self.assertEqual([c.value for c in candidates["subtotal"]], ["100"])
        self.assertEqual([c.value for c in candidates["tax_amount"]], ["8"])
        fields = extract_invoice(source, kie_run_id=KIE_RUN)["fields"]
        self.assertEqual(fields["total_amount"]["source_block_ids"], ["p0_b9"])

    def test_same_block_split_block_multiline_and_duplicate(self):
        source = evidence(
            [
                ("INVOICE", 0.4, 0.10),
                ("Seller: Company A", 0.05, 0.15),
                ("Ltd", 0.05, 0.17),
                ("Address: 1 Example Road", 0.05, 0.20),
                ("City", 0.05, 0.22),
                ("Invoice number:", 0.05, 0.27),
                ("001", 0.4, 0.27),
                ("Invoice number: 002", 0.05, 0.75),
            ]
        )
        fields = extract_invoice(source, kie_run_id=KIE_RUN)["fields"]
        self.assertEqual(fields["seller_name"]["normalized_value"], "Company A Ltd")
        self.assertEqual(
            fields["seller_address"]["normalized_value"], "1 Example Road City"
        )
        self.assertEqual(fields["invoice_number"]["value_status"], "AMBIGUOUS")
        self.assertEqual(
            set(fields["invoice_number"]["source_block_ids"]),
            {"p0_b5", "p0_b6", "p0_b7"},
        )

    def test_unassigned_generic_tax_id_and_no_ocr_repair(self):
        fields = extract_invoice(
            evidence(
                [
                    ("MST: O101234567", 0.05, 0.15),
                    ("Total: 1O0", 0.05, 0.80),
                    ("Currency: VND", 0.05, 0.84),
                ]
            ),
            kie_run_id=KIE_RUN,
        )["fields"]
        for name in ("seller_tax_id", "buyer_tax_id"):
            self.assertEqual(fields[name]["value_status"], "AMBIGUOUS")
            self.assertIn("SOURCE_ROLE_UNCLEAR", fields[name]["review_reasons"])
        self.assertIsNone(fields["total_amount"]["normalized_value"])


class LayoutHeaderTests(unittest.TestCase):
    def test_saved_reader_pdf_and_ocr_evidence_contract(self):
        directory = Path(__file__).parent / "fixtures/kie49/reader-tv2"
        for name in ("text_pdf", "clean_png", "blur_png", "clean_pdf"):
            with self.subTest(name=name):
                source = json.loads((directory / f"{name}.json").read_text())
                original = copy.deepcopy(source)
                baseline = extract_invoice(source, kie_run_id=KIE_RUN)
                variant = extract_with_layout(source, kie_run_id=KIE_RUN)
                self.assertEqual(source, original)
                self.assertEqual(baseline["line_items"], variant["line_items"])
                self.assertEqual(baseline["tax_breakdown"], variant["tax_breakdown"])
                ids = {block.block_id for block in flatten(source)}
                for cell in variant["fields"].values():
                    self.assertTrue(set(cell["source_block_ids"]) <= ids)
                if name == "text_pdf":
                    number = variant["fields"]["invoice_number"]
                    self.assertEqual(
                        baseline["fields"]["invoice_number"]["value_status"],
                        "AMBIGUOUS",
                    )
                    self.assertEqual(number["value_status"], "PRESENT")
                    self.assertEqual(number["normalized_value"], "00000001")
                    self.assertIn("MULTIPLE_CANDIDATES", number["review_reasons"])

    def test_region_priority_resolves_duplicates_and_keeps_evidence(self):
        source = evidence(
            [
                ("Currency: VND", 0.05, 0.04),
                ("Invoice number: 001", 0.05, 0.10),
                ("Total: 999", 0.05, 0.18),
                ("Description", 0.05, 0.35),
                ("Quantity", 0.45, 0.35),
                ("Amount", 0.75, 0.35),
                ("Service", 0.05, 0.40),
                ("1", 0.45, 0.40),
                ("100", 0.75, 0.40),
                ("Invoice number: 002", 0.05, 0.66),
                ("Total: 108", 0.05, 0.78),
            ]
        )
        before = copy.deepcopy(source)
        baseline = extract_invoice(source, kie_run_id=KIE_RUN)
        variant = extract_with_layout(source, kie_run_id=KIE_RUN)
        self.assertEqual(source, before)
        self.assertEqual(variant["configuration"], LAYOUT_CONFIGURATION)
        self.assertEqual(baseline["line_items"], variant["line_items"])
        self.assertEqual(baseline["tax_breakdown"], variant["tax_breakdown"])
        self.assertEqual(
            baseline["fields"]["invoice_number"]["value_status"], "AMBIGUOUS"
        )
        self.assertEqual(
            baseline["fields"]["total_amount"]["value_status"], "AMBIGUOUS"
        )
        for field, expected, ids in (
            ("invoice_number", "001", {"p0_b1", "p0_b9"}),
            ("total_amount", 108, {"p0_b2", "p0_b10"}),
        ):
            cell = variant["fields"][field]
            self.assertEqual(cell["value_status"], "PRESENT")
            self.assertEqual(cell["normalized_value"], expected)
            self.assertEqual(set(cell["source_block_ids"]), ids)
            self.assertIn("MULTIPLE_CANDIDATES", cell["review_reasons"])
            self.assertTrue(cell["machine_needs_review"])
        gold = {
            "fields": {
                field: {"annotation_status": "UNKNOWN", "normalized_value": None}
                for field in HEADER_FIELDS
            },
            "line_items": [],
        }
        gold["fields"]["invoice_number"] = {
            "annotation_status": "PRESENT",
            "normalized_value": "001",
        }
        gold["fields"]["total_amount"] = {
            "annotation_status": "PRESENT",
            "normalized_value": 108,
        }
        left, right = metrics([(baseline, gold)]), metrics([(variant, gold)])
        self.assertEqual(left["header_micro_accuracy"], 0)
        self.assertEqual(right["header_micro_accuracy"], 1)
        self.assertEqual(left["header_coverage"]["scored"], 2)

    def test_wrong_region_hint_cannot_remove_sole_candidate(self):
        source = evidence(
            [
                ("Invoice number: 007", 0.05, 0.85),
                ("Total: 42", 0.05, 0.12),
                ("Currency: VND", 0.05, 0.90),
            ]
        )
        result = extract_with_layout(source, kie_run_id=KIE_RUN)
        self.assertEqual(result["fields"]["invoice_number"]["normalized_value"], "007")
        self.assertEqual(result["fields"]["total_amount"]["normalized_value"], 42)
        self.assertEqual(result["fields"]["currency"]["normalized_value"], "VND")


if __name__ == "__main__":
    unittest.main()
