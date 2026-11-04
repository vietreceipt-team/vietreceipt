"""Synthetic software checks for the independent Footer Extractor V1."""

import copy
import unittest

from ai.kie.v2 import extract_invoice
from ai.kie.v2.consistency import check
from ai.kie.v2.contract import validate_result
from ai.kie.v2.footer import extract_footer
from tests.kie_v2_fixtures import KIE_RUN, document, evidence, invoice

REGION = {"page": 0, "bbox": [0.05, 0.65, 0.95, 0.95]}


class FooterExtractorTests(unittest.TestCase):
    def test_split_labels_match_right_hand_amounts_by_row(self):
        source = evidence(
            [
                ("Tổng thanh toán: 999999", 0.10, 0.20),
                ("108.000đ", 0.75, 0.83),
                ("TỔNG TIỀN HÀNG", 0.32, 0.70, 0.30),
                ("100.000", 0.75, 0.701),
                ("VAT", 0.32, 0.76),
                ("8%", 0.58, 0.76, 0.05),
                ("8.000", 0.75, 0.76),
                ("Tổng thanh toán", 0.32, 0.83, 0.30),
                ("495.000", 0.10, 0.83),
                ("1.250.000đ", 0.75, 0.87),
            ]
        )
        original = copy.deepcopy(source)
        fields = extract_footer(source, REGION)
        self.assertEqual(source, original)
        self.assertEqual(
            {key: cell["normalized_value"] for key, cell in fields.items()},
            {"subtotal": 100000, "tax_amount": 8000, "total_amount": 108000},
        )
        self.assertEqual(fields["total_amount"]["source_block_ids"], ["p0_b1", "p0_b7"])
        self.assertEqual(
            fields["total_amount"]["raw_text"], "108.000đ\nTổng thanh toán"
        )
        source["blocks"].reverse()
        self.assertEqual(extract_footer(source, REGION), fields)

    def test_inline_values_normalize_and_ignore_non_amount_rows(self):
        fields = extract_footer(
            evidence(
                [
                    ("Tong tien hang: 1 250 000", 0.08, 0.70, 0.55),
                    ("VAT (0%): 0", 0.08, 0.74),
                    ("Tổng phải thanh toán：1.250.000đ", 0.08, 0.78, 0.55),
                    ("Tổng thanh toán bằng chữ:", 0.08, 0.82, 0.45),
                    ("2000000", 0.75, 0.82),
                    ("Tiền khách đưa: 2000000", 0.08, 0.86, 0.55),
                ]
            ),
            REGION,
        )
        self.assertEqual(fields["subtotal"]["normalized_value"], 1250000)
        self.assertEqual(fields["tax_amount"]["normalized_value"], 0)
        total = fields["total_amount"]
        self.assertEqual(total["normalized_value"], 1250000)
        self.assertEqual(total["predicted_value"], "1.250.000đ")
        self.assertEqual(total["source_block_ids"], ["p0_b2"])

    def test_region_filters_page_and_rejects_invalid_or_cut_regions(self):
        source = document(
            evidence([("Total: 999", 0.10, 0.72)]),
            evidence(
                [
                    ("Total: 123", 0.10, 0.72),
                    ("Subtotal: 555", 0.01, 0.78, 0.03),
                ],
                prefix="p1",
            ),
        )
        fields = extract_footer(source, {**REGION, "page": 1})
        self.assertEqual(fields["total_amount"]["normalized_value"], 123)
        self.assertEqual(fields["total_amount"]["source_block_ids"], ["p1_b0"])
        self.assertEqual(fields["subtotal"]["value_status"], "UNKNOWN")
        for region in (
            {**REGION, "page": 2},
            {**REGION, "page": True},
            {**REGION, "bbox": [0.05, 0.727, 0.95, 0.95]},
            {**REGION, "bbox": [0.05, 0.9, 0.95, 0.8]},
            {**REGION, "bbox": [0.05, float("nan"), 0.95, 0.95]},
        ):
            with self.subTest(region=region), self.assertRaises(ValueError):
                extract_footer(source, region)

    def test_conflicting_amounts_require_review_and_labels_bound_search(self):
        fields = extract_footer(
            evidence(
                [
                    ("VAT:", 0.08, 0.70, 0.06),
                    ("8.000", 0.20, 0.70, 0.08),
                    ("Tổng thanh toán", 0.35, 0.70, 0.20),
                    ("108.000", 0.60, 0.70, 0.10),
                    ("118.000", 0.78, 0.70, 0.10),
                    ("Cộng tiền hàng:", 0.08, 0.74, 0.20),
                    ("Khách đưa:", 0.42, 0.74, 0.15),
                    ("200000", 0.75, 0.74),
                ]
            ),
            REGION,
        )
        self.assertEqual(fields["tax_amount"]["normalized_value"], 8000)
        self.assertEqual(fields["tax_amount"]["source_block_ids"], ["p0_b0", "p0_b1"])
        self.assertIsNone(fields["subtotal"]["normalized_value"])
        total = fields["total_amount"]
        self.assertIsNone(total["normalized_value"])
        self.assertEqual(total["value_status"], "AMBIGUOUS")
        self.assertTrue(total["machine_needs_review"])
        self.assertIn("MULTIPLE_CANDIDATES", total["review_reasons"])
        self.assertEqual(total["source_block_ids"], ["p0_b2", "p0_b3", "p0_b4"])

    def test_missing_rate_only_and_unreadable_amounts_stay_distinct(self):
        fields = extract_footer(
            evidence(
                [
                    ("VAT: 8%", 0.08, 0.72),
                    ("Tổng thanh toán", 0.08, 0.76, 0.30),
                    ("10?.000", 0.75, 0.76),
                    ("108.000", 0.75, 0.80),
                ]
            ),
            REGION,
        )
        tax = fields["tax_amount"]
        self.assertEqual(tax["value_status"], "UNKNOWN")
        self.assertEqual(tax["source_block_ids"], ["p0_b0"])
        self.assertIn("NO_CANDIDATE", tax["review_reasons"])
        self.assertEqual(fields["subtotal"]["source_block_ids"], [])
        total = fields["total_amount"]
        self.assertEqual(total["value_status"], "UNREADABLE")
        self.assertIsNone(total["normalized_value"])
        self.assertIn("UNREADABLE_SOURCE", total["review_reasons"])
        for invalid in ("108.00", "-108.000", "108 USD"):
            with self.subTest(invalid=invalid):
                source = evidence([(f"Total: {invalid}", 0.1, 0.7)])
                cell = extract_footer(source, REGION)["total_amount"]
                self.assertEqual(cell["value_status"], "AMBIGUOUS")
                self.assertIsNone(cell["normalized_value"])

    def test_consistency_and_v2_contract(self):
        for amount, warning in [(108000, False), (108001, False), (118000, True)]:
            with self.subTest(amount=amount):
                source = invoice(total=str(amount))
                fields = extract_footer(source, REGION)
                self.assertEqual(fields["total_amount"]["normalized_value"], amount)
                for cell in fields.values():
                    self.assertEqual(
                        "CONSISTENCY_WARNING" in cell["review_reasons"], warning
                    )
                    self.assertEqual(cell["machine_needs_review"], warning)
                result = extract_invoice(source, kie_run_id=KIE_RUN)
                result["fields"].update(fields)
                check(result)
                validate_result(result, source, kie_run_id=KIE_RUN)


if __name__ == "__main__":
    unittest.main()
