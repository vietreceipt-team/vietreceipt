"""Candidate alignment preserves source truth and never fabricates OCR IDs."""

import copy
import unittest
from scripts.data.build_tv4_handoff import align


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.gold = dict(
            receipt_id="source",
            fields={
                "seller_name": dict(
                    annotation_status="PRESENT",
                    raw_value="Công ty Mẫu",
                    normalized_value="Công ty Mẫu",
                    source_block_ids=[],
                )
            },
            line_items=[],
        )
        self.regions = [
            dict(
                cell="fields.seller_name",
                bounds=[0.1, 0.1, 0.6, 0.2],
                selected_value_text="Công ty Mẫu",
            )
        ]
        self.evidence = dict(
            receipt_id="input-alias",
            pages=[
                dict(
                    page_index=0,
                    evidence=dict(
                        blocks=[
                            dict(
                                block_id="actual-test-block",
                                text="Công ty Mẫu",
                                reading_order=0,
                                polygon=[
                                    {"x": 0.1, "y": 0.1},
                                    {"x": 0.6, "y": 0.1},
                                    {"x": 0.6, "y": 0.2},
                                    {"x": 0.1, "y": 0.2},
                                ],
                            )
                        ]
                    ),
                )
            ],
        )

    def test_links_only_actual_block_ids(self):
        before = copy.deepcopy(self.gold)
        gold, rows = align(self.gold, self.regions, self.evidence)
        self.assertEqual(
            gold["fields"]["seller_name"]["source_block_ids"], ["actual-test-block"]
        )
        self.assertEqual(rows[0]["status"], "CANDIDATE_REQUIRES_REVIEW")
        self.assertEqual(self.gold, before)

    def test_missing_ocr_preserves_present_gold(self):
        self.evidence["pages"][0]["evidence"]["blocks"] = []
        gold, rows = align(self.gold, self.regions, self.evidence)
        self.assertEqual(gold["fields"]["seller_name"]["annotation_status"], "PRESENT")
        self.assertEqual(
            gold["fields"]["seller_name"]["normalized_value"], "Công ty Mẫu"
        )
        self.assertEqual(rows[0]["status"], "UNALIGNED")
        self.assertEqual(gold["fields"]["seller_name"]["source_block_ids"], [])

    def test_wrong_ocr_text_keeps_spatial_candidate_for_review(self):
        self.evidence["pages"][0]["evidence"]["blocks"][0]["text"] = "Cong ty Mau"
        gold, rows = align(self.gold, self.regions, self.evidence)
        self.assertEqual(rows[0]["status"], "SPATIAL_CANDIDATE_REQUIRES_REVIEW")
        self.assertEqual(rows[0]["candidate_block_ids"], ["actual-test-block"])
        self.assertEqual(
            gold["fields"]["seller_name"]["source_block_ids"], ["actual-test-block"]
        )
        self.assertEqual(gold["fields"]["seller_name"]["raw_value"], "Công ty Mẫu")

    def test_public_raw_text_currency_marker_does_not_infer_currency(self):
        from scripts.data.prepare_public import map_native

        fields, items, mask = map_native(
            "sroie_curated",
            {
                "entities": {"company": "UNIT", "total": "$8.20"},
                "words": ["UNIT"],
                "bboxes": [[0, 0, 1, 1]],
            },
        )
        self.assertEqual(fields["total_amount"]["normalized_value"], 8.2)
        self.assertEqual(fields["total_amount"]["raw_value"], "$8.20")
        self.assertEqual(fields["currency"]["annotation_status"], "UNKNOWN")
        self.assertNotIn("currency", mask)

    def test_public_empty_total_remains_unavailable(self):
        from scripts.data.prepare_public import map_native

        fields, items, mask = map_native("sroie", {"company": "UNIT", "total": ""})
        self.assertNotIn("total_amount", mask)
        self.assertEqual(fields["total_amount"]["annotation_status"], "UNKNOWN")

    def test_vietnamese_decimal_quantity_and_raw_thousands_retained(self):
        from scripts.data.prepare_public import map_native

        fields, items, mask = map_native(
            "vietnamese_bill",
            {
                "master_data": [
                    dict(ten_dich_vu="UNIT", so_luong="0.5", thanh_tien="510.000đ")
                ]
            },
        )
        self.assertEqual(items[0]["quantity"]["normalized_value"], 0.5)
        self.assertEqual(items[0]["amount"]["normalized_value"], 510000)
        self.assertEqual(items[0]["amount"]["raw_value"], "510.000đ")


if __name__ == "__main__":
    unittest.main()
