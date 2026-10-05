"""Synthetic unit/integration checks only; no empirical accuracy claims."""

import copy
import importlib
import unittest
from uuid import UUID

from jsonschema import ValidationError

from ai.kie.v2 import extract_invoice
from ai.kie.v2.config import HEADER_FIELDS
from ai.kie.v2.contract import cells, validate_result, validator
from ai.kie.v2.evidence import flatten
from ai.kie.v2.normalization import normalize
from tests.kie_v2_fixtures import KIE_RUN, document, evidence, invoice


class InvoiceV2Tests(unittest.TestCase):
    def test_pdf_separate_colon_and_adjacent_identifier_tokens(self):
        fields = self.extract(
            evidence(
                [
                    ("Date", 0.1, 0.1),
                    (": 21st Sep 2026", 0.4, 0.1, 0.3),
                    ("Invoice No.", 0.1, 0.2),
                    (": 082026", 0.4, 0.2, 0.1),
                    ("UCHAT -", 0.51, 0.2, 0.15),
                ]
            )
        )["fields"]
        self.assertEqual(fields["invoice_date"]["normalized_value"], "2026-09-21")
        self.assertEqual(fields["invoice_date"]["raw_text"], "Date\n: 21st Sep 2026")
        self.assertEqual(fields["invoice_number"]["normalized_value"], "082026 UCHAT -")
        self.assertTrue(fields["invoice_number"]["machine_needs_review"])

    def test_vietnamese_pos_labels_and_reviewed_currency_inference(self):
        source = evidence(
            [
                ("Cöng ty TNHH Cong Nghe", 0.2, 0.03, 0.5),
                ("Example Viet Nam", 0.25, 0.055, 0.35),
                ("DC123Example Road", 0.2, 0.09, 0.5),
                ("HOA DON BANHANG", 0.2, 0.15, 0.5),
                ("Ngay:07/11/2022", 0.1, 0.2),
                ("sphieu12345678", 0.55, 0.2),
                ("Khäch hangANH MAU", 0.1, 0.25, 0.5),
                ("Mat hang", 0.1, 0.35),
                ("SL", 0.4, 0.35),
                ("DVT", 0.5, 0.35),
                ("Gia", 0.65, 0.35),
                ("T tien", 0.8, 0.35),
                ("San pham mau", 0.1, 0.4),
                ("1", 0.4, 0.4),
                ("cai", 0.5, 0.4),
                ("1,234,000", 0.65, 0.4),
                ("1,234,000", 0.8, 0.4),
                ("Tong SL", 0.1, 0.45),
                ("1", 0.4, 0.45),
                ("Tien hang:", 0.1, 0.5),
                ("1,234,000", 0.8, 0.5),
                ("Tong:", 0.1, 0.55),
                ("1,234,000", 0.8, 0.55),
            ]
        )
        result = self.extract(source)
        fields = result["fields"]
        self.assertEqual(fields["invoice_number"]["normalized_value"], "12345678")
        self.assertEqual(fields["invoice_date"]["normalized_value"], "2022-11-07")
        self.assertEqual(fields["buyer_name"]["normalized_value"], "ANH MAU")
        self.assertEqual(fields["total_amount"]["normalized_value"], 1234000)
        self.assertTrue(fields["currency"]["machine_needs_review"])
        self.assertTrue(fields["seller_name"]["machine_needs_review"])
        self.assertEqual(len(result["line_items"]), 1)
        self.assertIsNone(fields["tax_amount"]["normalized_value"])

    def extract(self, source=None):
        return extract_invoice(
            source if source is not None else invoice(), kie_run_id=KIE_RUN
        )

    def field(self, label, name, currency="VND"):
        return self.extract(
            evidence([(label, 0.05, 0.1), (f"Currency: {currency}", 0.05, 0.2)])
        )["fields"][name]

    def test_all_thirteen_headers(self):
        result = self.extract()
        self.assertEqual(set(result["fields"]), set(HEADER_FIELDS))
        self.assertTrue(
            all(c["value_status"] == "PRESENT" for c in result["fields"].values()),
            result["fields"],
        )
        self.assertEqual(
            result["fields"]["invoice_number"]["normalized_value"], "0000049"
        )
        self.assertEqual(result["fields"]["total_amount"]["normalized_value"], 108000)

    def test_roles_tax_ids(self):
        fields = self.extract()["fields"]
        self.assertEqual(fields["seller_tax_id"]["normalized_value"], "0101234567")
        self.assertEqual(fields["buyer_tax_id"]["normalized_value"], "0201234567")
        self.assertIn("Tổng Hợp", fields["seller_name"]["normalized_value"])
        self.assertIn("Khách Mẫu", fields["buyer_name"]["normalized_value"])

    def test_unknown_role(self):
        fields = self.extract(evidence([("MST: 0101234567", 0.1, 0.1)]))["fields"]
        for name in ("seller_tax_id", "buyer_tax_id"):
            self.assertEqual(fields[name]["value_status"], "AMBIGUOUS")
            self.assertIn("SOURCE_ROLE_UNCLEAR", fields[name]["review_reasons"])

    def test_side_by_side_roles_with_interleaved_reading_order(self):
        source = evidence(
            [
                ("Seller: Công ty Mẫu A", 0.05, 0.1),
                ("Buyer: Công ty Mẫu B", 0.55, 0.1),
                ("MST: 0101234567", 0.05, 0.15),
                ("MST: 0201234567", 0.55, 0.15),
            ]
        )
        fields = self.extract(source)["fields"]
        self.assertEqual(fields["seller_tax_id"]["normalized_value"], "0101234567")
        self.assertEqual(fields["buyer_tax_id"]["normalized_value"], "0201234567")

    def test_tax_branch_identifier(self):
        cell = self.field("Seller tax ID: 0101234567-001", "seller_tax_id")
        self.assertEqual(cell["normalized_value"], "0101234567001")
        self.assertEqual(cell["normalization"]["rule"], "tax_id_printed_separators")

    def test_invalid_transport_and_geometry(self):
        for text in ("Invoice number: 001\x00", "Invoice number: 001\ud800"):
            with self.assertRaises(ValueError):
                self.extract(evidence([(text, 0.1, 0.1)]))
        source = invoice()
        source["blocks"][0]["confidence"] = float("nan")
        with self.assertRaises(ValueError):
            self.extract(source)
        source = invoice()
        source["blocks"][0]["polygon"] = [{"x": 0.1, "y": 0.1}] * 4
        with self.assertRaises(ValueError):
            self.extract(source)

    def test_statuses(self):
        self.assertEqual(
            self.field("Buyer name: Không có", "buyer_name")["value_status"],
            "NOT_PRESENT",
        )
        self.assertEqual(
            self.field("Seller tax ID: 01012??567", "seller_tax_id")["value_status"],
            "UNREADABLE",
        )
        self.assertEqual(
            self.field("Số hóa đơn:", "invoice_number")["value_status"], "UNREADABLE"
        )
        self.assertEqual(
            self.extract(evidence([]))["fields"]["invoice_number"]["value_status"],
            "UNKNOWN",
        )
        self.assertEqual(
            self.field("Date: 09/10/2026", "invoice_date")["value_status"], "AMBIGUOUS"
        )

    def test_date_rules(self):
        for value, expected in [
            ("2026-09-19", "2026-09-19"),
            ("19/09/2026", "2026-09-19"),
            ("09/19/2026", "2026-09-19"),
            ("31/02/2026", None),
            ("09/10/2026", None),
            ("19/09/26", None),
        ]:
            with self.subTest(value=value):
                self.assertEqual(
                    self.field("Date: " + value, "invoice_date")["normalized_value"],
                    expected,
                )
        self.assertEqual(
            self.field("Ngày 09 tháng 10 năm 2026", "invoice_date")["normalized_value"],
            "2026-10-09",
        )

    def test_money_rules(self):
        for value in [
            "1.080.000",
            "1,080,000",
            "1 080 000",
            "1080000",
            "1.080.000 VNĐ",
        ]:
            with self.subTest(value=value):
                self.assertEqual(
                    self.field("Total: " + value, "total_amount")["normalized_value"],
                    1080000,
                )
        for value in ["1.08", "1,080.000", "-100", "O000"]:
            with self.subTest(value=value):
                self.assertIsNone(
                    self.field("Total: " + value, "total_amount")["normalized_value"]
                )

    def test_currency_required_and_unsupported(self):
        for currency in ["EUR", "JPY"]:
            result = self.extract(
                evidence(
                    [("Total: 100", 0.1, 0.1), ("Currency: " + currency, 0.1, 0.2)]
                )
            )
            self.assertIsNone(result["fields"]["total_amount"]["normalized_value"])
            self.assertIn(
                "UNSUPPORTED_CURRENCY", result["fields"]["currency"]["review_reasons"]
            )
        self.assertIsNone(
            self.extract(evidence([("Total: 1.080", 0.1, 0.1)]))["fields"][
                "total_amount"
            ]["normalized_value"]
        )

    def test_usd_money_and_english_calendar_dates(self):
        for value, expected in [
            ("349 USD", 349),
            ("USD 1,234.56", 1234.56),
            ("0.05", 0.05),
        ]:
            self.assertEqual(
                self.field("Total: " + value, "total_amount", currency="USD")[
                    "normalized_value"
                ],
                expected,
            )
        for value in ["1.234", "1,23", "349 VND", "NaN", "-1"]:
            self.assertIsNone(
                self.field("Total: " + value, "total_amount", currency="USD")[
                    "normalized_value"
                ]
            )
        for value, expected in [
            ("21st Sep 2026", "2026-09-21"),
            ("2nd October 2026", "2026-10-02"),
            ("29th Feb 2024", "2024-02-29"),
        ]:
            self.assertEqual(
                self.field("Date: " + value, "invoice_date")["normalized_value"],
                expected,
            )
        for value in ["31st Sep 2026", "29th Feb 2025", "21st Other 2026"]:
            self.assertIsNone(
                self.field("Date: " + value, "invoice_date")["normalized_value"]
            )

    def test_english_service_invoice_preserves_roles_and_missing_fields(self):
        source = evidence(
            [
                ("Example Service Joint Stock Company", 0.05, 0.02, 0.5),
                ("Address: 1 Example Road,", 0.05, 0.045, 0.4),
                ("Example City", 0.05, 0.07, 0.25),
                ("INVOICE", 0.4, 0.13),
                ("To: Sample Client", 0.05, 0.2, 0.35),
                ("LDA (SAMPLE)", 0.05, 0.225, 0.25),
                ("Taxcode: 7654321", 0.05, 0.27),
                ("Date: 3rd Oct 2026", 0.55, 0.27, 0.4),
                ("Revenue Sharing of the service", 0.05, 0.4, 0.4),
                ("Amount", 0.7, 0.4),
                ("(SERVICE 25%)", 0.05, 0.425),
                ("Example chat service", 0.05, 0.46, 0.4),
                ("123.45 USD", 0.7, 0.46),
                ("of Sep 2026", 0.05, 0.485),
                ("Total", 0.05, 0.53),
                ("123.45 USD", 0.7, 0.53),
                ("Please remit payment to:", 0.05, 0.62, 0.4),
                ("Beneficiary: Another Account", 0.05, 0.65, 0.4),
                ("Address: Other bank address", 0.05, 0.68, 0.4),
            ]
        )
        result = self.extract(source)
        fields = result["fields"]
        self.assertEqual(
            fields["seller_name"]["normalized_value"],
            "Example Service Joint Stock Company",
        )
        self.assertTrue(fields["seller_name"]["machine_needs_review"])
        self.assertEqual(
            fields["seller_address"]["normalized_value"], "1 Example Road, Example City"
        )
        self.assertEqual(
            fields["buyer_name"]["normalized_value"], "Sample Client LDA (SAMPLE)"
        )
        self.assertEqual(fields["buyer_tax_id"]["normalized_value"], "7654321")
        self.assertEqual(fields["total_amount"]["normalized_value"], 123.45)
        self.assertEqual(fields["currency"]["normalized_value"], "USD")
        self.assertEqual(fields["tax_amount"]["value_status"], "UNKNOWN")
        self.assertEqual(len(result["line_items"]), 1)
        self.assertEqual(result["line_items"][0]["amount"]["normalized_value"], 123.45)
        self.assertEqual(result["tax_breakdown"], [])

    def test_unicode_and_identifier_normalization(self):
        self.assertEqual(
            self.field("Seller name:  Công  ty Mẫu  ", "seller_name")[
                "normalized_value"
            ],
            "Công ty Mẫu",
        )
        for field in ("invoice_number", "invoice_symbol", "invoice_template_number"):
            value, provenance, reason = normalize(field, " 001-AA/26 ", "", None)
            self.assertEqual(value, "001-AA/26")
            self.assertTrue(provenance["version"])
            self.assertIsNone(reason)

    def test_multiple_candidates(self):
        source = evidence(
            [("Số hóa đơn: 001", 0.1, 0.1), ("Số hóa đơn: 002", 0.1, 0.2)]
        )
        cell = self.extract(source)["fields"]["invoice_number"]
        self.assertEqual(cell["value_status"], "AMBIGUOUS")
        self.assertEqual(len(cell["source_block_ids"]), 2)

    def test_separate_label_value_geometry(self):
        source = evidence(
            [("Invoice number:", 0.1, 0.1), ("00009", 0.5, 0.1), ("99999", 0.5, 0.3)]
        )
        self.assertEqual(
            self.extract(source)["fields"]["invoice_number"]["normalized_value"],
            "00009",
        )

    def test_pdf_sentinel_is_not_field_confidence(self):
        source = invoice()
        source["engine"]["name"] = "pdfium-text"
        for block in source["blocks"]:
            block["confidence"] = 1.0
        self.assertTrue(all(b.evidence_confidence is None for b in flatten(source)))
        self.assertTrue(
            all(
                c["confidence"] is None and c["heuristic_score"] < 1
                for c in cells(self.extract(source))
            )
        )

    def test_low_ocr_quality_penalty(self):
        source = evidence([("Invoice number: 001", 0.1, 0.1)])
        source["blocks"][0]["confidence"] = 0.1
        cell = self.extract(source)["fields"]["invoice_number"]
        self.assertLess(cell["heuristic_score"], 0.95)
        self.assertEqual(cell["value_status"], "PRESENT")
        self.assertIn("LOW_CONFIDENCE", cell["review_reasons"])

    def test_one_row(self):
        result = self.extract()
        self.assertEqual(len(result["line_items"]), 1)
        row = result["line_items"][0]
        self.assertEqual(row["quantity"]["normalized_value"], 2)
        self.assertEqual(row["amount"]["normalized_value"], 100000)
        self.assertFalse(row["machine_needs_review"])

    def test_multiple_rows_and_decimal_quantity(self):
        rows = [
            ["Hàng mẫu A", "kg", "1,5", "40000", "60000"],
            ["Hàng mẫu B", "kg", "2.0", "20000", "40000"],
        ]
        result = self.extract(invoice(rows=rows))
        self.assertEqual(len(result["line_items"]), 2)
        self.assertEqual(result["line_items"][0]["quantity"]["normalized_value"], 1.5)
        self.assertEqual(result["consistency"]["checks"][0]["status"], "PASS")

    def test_missing_unit_column_and_missing_cell(self):
        row = self.extract(invoice(unit=False))["line_items"][0]
        self.assertEqual(row["unit"]["value_status"], "NOT_PRESENT")
        row = self.extract(invoice(rows=[["Hàng mẫu", None, "1", "100000", "100000"]]))[
            "line_items"
        ][0]
        self.assertEqual(row["unit"]["value_status"], "UNKNOWN")
        self.assertTrue(row["machine_needs_review"])

    def test_multiline_description(self):
        source = invoice(
            rows=[
                ["Dịch vụ tư vấn", "gói", "1", "100000", "100000"],
                ["triển khai hệ thống", None, None, None, None],
            ]
        )
        # Continuation closely below baseline, while preserving exact raw blocks.
        block = next(b for b in source["blocks"] if b["text"] == "triển khai hệ thống")
        for point in block["polygon"]:
            point["y"] -= 0.025
        rows = self.extract(source)["line_items"]
        self.assertEqual(len(rows), 1)
        self.assertIn("triển khai", rows[0]["description"]["normalized_value"])
        self.assertEqual(len(rows[0]["description"]["source_block_ids"]), 2)
        self.assertIn("AMBIGUOUS_FORMAT", rows[0]["review_reasons"])

    def test_partial_unreadable_row(self):
        rows = self.extract(invoice(rows=[["???", None, "1", None, "10??00"]]))[
            "line_items"
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["description"]["value_status"], "UNREADABLE")
        self.assertEqual(rows[0]["amount"]["value_status"], "UNREADABLE")
        self.assertTrue(rows[0]["machine_needs_review"])

    def test_noisy_misaligned_columns(self):
        source = invoice(rows=[["Dịch vụ mẫu", "gói", "2", "5O000", "100000"]])
        for block in source["blocks"]:
            if block["text"] == "2":
                for point in block["polygon"]:
                    point["x"] += 0.022
                    point["y"] += 0.005
        rows = self.extract(source)["line_items"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["quantity"]["normalized_value"], 2)
        self.assertIsNone(rows[0]["unit_price"]["normalized_value"])
        self.assertTrue(rows[0]["machine_needs_review"])

    def test_empty_table(self):
        self.assertEqual(self.extract(invoice(rows=[]))["line_items"], [])

    def test_layout_translation_and_source_list_shuffle(self):
        source = invoice()
        expected = self.extract(source)
        for block in source["blocks"]:
            for point in block["polygon"]:
                point["x"] = point["x"] * 0.85 + 0.04
                point["y"] = point["y"] * 0.9 + 0.02
        source["blocks"].reverse()
        self.assertEqual(self.extract(source), expected)

    def test_vnd_currency_markers(self):
        for marker in ("VND", "VNĐ", "đ", "₫", "đồng"):
            with self.subTest(marker=marker):
                self.assertEqual(
                    self.field("Total: 1000", "total_amount", currency=marker)[
                        "normalized_value"
                    ],
                    1000,
                )

    def test_competing_currency_cannot_be_outscored(self):
        source = evidence([("Currency: USD", 0.1, 0.1), ("Total: 100 VND", 0.1, 0.2)])
        fields = self.extract(source)["fields"]
        self.assertEqual(fields["currency"]["value_status"], "AMBIGUOUS")
        self.assertIn("MULTIPLE_CANDIDATES", fields["currency"]["review_reasons"])
        self.assertIsNone(fields["total_amount"]["normalized_value"])

    def test_nonstandard_tax_category(self):
        source = evidence(
            [
                ("Currency: VND", 0.1, 0.02),
                ("VAT KCT; Taxable amount: 100000", 0.1, 0.1),
            ]
        )
        group = self.extract(source)["tax_breakdown"][0]
        self.assertEqual(group["rate"]["normalized_value"], "kct")
        self.assertEqual(group["tax_amount"]["value_status"], "UNKNOWN")

    def test_consistency_one_vnd_tolerance(self):
        result = self.extract(invoice(total="108001"))
        self.assertEqual(result["consistency"]["checks"][1]["status"], "PASS")
        self.assertEqual(result["fields"]["total_amount"]["normalized_value"], 108001)

    def test_tax_table(self):
        taxes = self.extract(invoice(tax_groups=True))["tax_breakdown"]
        self.assertEqual(len(taxes), 1)
        self.assertEqual(taxes[0]["rate"]["normalized_value"], "8%")
        self.assertEqual(taxes[0]["taxable_amount"]["normalized_value"], 100000)

    def test_multiple_tax_rates(self):
        source = evidence(
            [("Currency: VND", 0.1, 0.02)]
            + [
                (
                    f"VAT {rate}%; Taxable amount: 100000; Tax amount: {rate * 1000}",
                    0.1,
                    0.1 + index * 0.1,
                )
                for index, rate in enumerate([0, 5, 8, 10])
            ]
        )
        taxes = self.extract(source)["tax_breakdown"]
        self.assertEqual(
            [t["rate"]["normalized_value"] for t in taxes], ["0%", "5%", "8%", "10%"]
        )
        self.assertEqual(
            [t["tax_amount"]["normalized_value"] for t in taxes], [0, 5000, 8000, 10000]
        )

    def test_consistency_pass_fail_no_mutation(self):
        good, bad = self.extract(), self.extract(invoice(total="118000"))
        self.assertEqual(
            [c["status"] for c in good["consistency"]["checks"]], ["PASS", "PASS"]
        )
        self.assertEqual(bad["fields"]["total_amount"]["normalized_value"], 118000)
        self.assertEqual(bad["fields"]["total_amount"]["predicted_value"], "118000")
        self.assertIn(
            "CONSISTENCY_WARNING", bad["fields"]["total_amount"]["review_reasons"]
        )

    def test_line_sum_warning(self):
        result = self.extract(invoice(rows=[["Mẫu", "gói", "1", "50000", "50000"]]))
        self.assertEqual(result["line_items"][0]["amount"]["normalized_value"], 50000)
        self.assertIn("CONSISTENCY_WARNING", result["line_items"][0]["review_reasons"])

    def test_multi_page_order_and_repeated_headers(self):
        first = evidence(
            [
                ("Currency: VND", 0.1, 0.02),
                ("Tên hàng", 0.05, 0.1),
                ("Thành tiền", 0.75, 0.1),
                ("Mẫu A", 0.05, 0.2),
                ("100", 0.75, 0.2),
            ]
        )
        second = evidence(
            [
                ("Tên hàng", 0.05, 0.1),
                ("Thành tiền", 0.75, 0.1),
                ("Mẫu B", 0.05, 0.2),
                ("200", 0.75, 0.2),
            ],
            prefix="p1",
        )
        result = self.extract(document(first, second))
        self.assertEqual(
            [r["description"]["normalized_value"] for r in result["line_items"]],
            ["Mẫu A", "Mẫu B"],
        )
        self.assertTrue(
            result["line_items"][1]["amount"]["source_block_ids"][0].startswith("p1")
        )

    def test_input_rejects_bad_identities_pages_orders_and_duplicates(self):
        source = document(invoice(), evidence([("Mẫu", 0.1, 0.1)], prefix="p1"))
        mutations = [
            lambda s: s["pages"][1].update(page_index=3),
            lambda s: s["pages"][1]["evidence"].update(ocr_run_id=str(KIE_RUN)),
            lambda s: s["pages"][1]["evidence"].update(receipt_id=str(KIE_RUN)),
            lambda s: s["pages"][1]["evidence"]["blocks"][0].update(block_id="p0_b0"),
            lambda s: s["pages"][0]["evidence"]["blocks"][0].update(reading_order=999),
            lambda s: s.update(receipt_id="bad"),
            lambda s: s.update(pages=[]),
        ]
        for mutate in mutations:
            bad = copy.deepcopy(source)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.extract(bad)

    def test_output_rejects_bad_linkage_and_run(self):
        source = invoice()
        result = self.extract(source)
        mutations = [
            lambda r: r.update(source_ocr_run_id=str(KIE_RUN)),
            lambda r: r.update(receipt_id=str(KIE_RUN)),
            lambda r: r["fields"]["invoice_number"].update(
                source_block_ids=["unknown"]
            ),
            lambda r: r["fields"]["invoice_number"].update(raw_text="modified"),
            lambda r: r["fields"]["invoice_number"].update(
                source_block_ids=["p0_b2", "p0_b2"]
            ),
        ]
        for mutate in mutations:
            bad = copy.deepcopy(result)
            mutate(bad)
            with (
                self.subTest(mutate=mutate),
                self.assertRaises((ValueError, ValidationError)),
            ):
                validate_result(bad, source, kie_run_id=KIE_RUN)

    def test_schema_required_metadata_and_no_human_state(self):
        result = self.extract()
        for key in (
            "predicted_value",
            "normalization",
            "review_policy_version",
            "machine_needs_review",
            "review_reasons",
            "heuristic_score",
            "score_version",
        ):
            bad = copy.deepcopy(result)
            del bad["fields"]["invoice_number"][key]
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validator().validate(bad)
        for key in ("extractor", "configuration"):
            bad = copy.deepcopy(result)
            del bad[key]
            with self.assertRaises(ValidationError):
                validator().validate(bad)
        bad = copy.deepcopy(result)
        del bad["line_items"][0]["review_policy_version"]
        with self.assertRaises(ValidationError):
            validator().validate(bad)
        bad = copy.deepcopy(result)
        bad["fields"]["invoice_number"]["corrected_value"] = "001"
        with self.assertRaises(ValidationError):
            validator().validate(bad)

    def test_schema_nonpresent_null_present_evidence(self):
        for status in ("UNKNOWN", "NOT_PRESENT", "UNREADABLE", "AMBIGUOUS"):
            result = self.extract()
            result["fields"]["invoice_number"]["value_status"] = status
            with self.subTest(status=status), self.assertRaises(ValidationError):
                validator().validate(result)
        result = self.extract()
        result["fields"]["invoice_number"]["source_block_ids"] = []
        with self.assertRaises(ValidationError):
            validator().validate(result)

    def test_determinism_immutability_provider_callable(self):
        source = invoice()
        original = copy.deepcopy(source)
        provider = importlib.import_module("ai.kie.v2").extract_invoice
        self.assertEqual(
            provider(source, kie_run_id=KIE_RUN), provider(source, kie_run_id=KIE_RUN)
        )
        self.assertEqual(source, original)
        with self.assertRaises(TypeError):
            provider(source, kie_run_id=str(KIE_RUN))
        with self.assertRaises(ValueError):
            validate_result(self.extract(), source, kie_run_id=UUID(int=7))


if __name__ == "__main__":
    unittest.main()
