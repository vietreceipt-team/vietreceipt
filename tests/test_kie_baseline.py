from __future__ import annotations

import unittest
from uuid import UUID

from ai.kie.candidates.invoice_id import (
    generate_invoice_id_candidates,
)
from ai.kie.candidates.merchant_address import (
    generate_merchant_address_candidates,
)
from ai.kie.candidates.total_amount import (
    generate_total_amount_candidates,
)
from ai.kie.contract import validate_kie_result
from ai.kie.models import Candidate, NormalizationResult
from ai.kie.normalization.invoice_id import normalize_invoice_id
from ai.kie.normalization.merchant_address import (
    normalize_merchant_address,
)
from ai.kie.normalization.receipt_date import normalize_receipt_date
from ai.kie.normalization.total_amount import normalize_total_amount
from ai.kie.pipeline import run_kie
from ai.kie.ranking.scorer import (
    rank_candidates,
    score_candidate,
)
from ai.kie.review import decide_review


RECEIPT_ID = "11111111-1111-4111-8111-111111111111"
OCR_RUN_ID = "22222222-2222-4222-8222-222222222222"
KIE_RUN_ID = UUID(
    "33333333-3333-4333-8333-333333333333"
)


def make_candidate(
    field_name: str,
    value: str,
    *,
    score: float = 0.90,
    raw_text: str | None = None,
    source_block_ids: tuple[str, ...] = ("b0",),
    positive: tuple[str, ...] = (),
    negative: tuple[str, ...] = (),
) -> Candidate:
    return Candidate(
        field_name=field_name,
        predicted_value=value,
        source_block_ids=source_block_ids,
        raw_text=raw_text if raw_text is not None else value,
        matched_positive_keywords=positive,
        matched_negative_keywords=negative,
        pattern_score=0.0,
        context_score=0.0,
        layout_score=0.0,
        ocr_score=0.95,
        final_score=score,
    )


def make_block(
    block_id: str,
    text: str,
    order: int,
    y: float,
    confidence: float = 0.95,
) -> dict:
    return {
        "block_id": block_id,
        "text": text,
        "confidence": confidence,
        "polygon": [
            {"x": 0.10, "y": y},
            {"x": 0.90, "y": y},
            {"x": 0.90, "y": y + 0.04},
            {"x": 0.10, "y": y + 0.04},
        ],
        "reading_order": order,
    }


def make_ocr(
    blocks: list[dict],
) -> dict:
    return {
        "schema_version": "1.3",
        "receipt_id": RECEIPT_ID,
        "ocr_run_id": OCR_RUN_ID,
        "engine": {
            "name": "test-ocr",
            "version": "0.1.0",
        },
        "image": {
            "width_px": 1000,
            "height_px": 1600,
        },
        "blocks": blocks,
        "average_confidence": (
            sum(
                float(block["confidence"])
                for block in blocks
            )
            / len(blocks)
            if blocks
            else 0.0
        ),
        "duration_ms": 100,
    }


class KIEBaselineTests(unittest.TestCase):

    # ------------------------------------------------------------------
    # 01. Valid date
    # ------------------------------------------------------------------

    def test_01_valid_date_normalizes_to_iso(self) -> None:
        result = normalize_receipt_date(
            make_candidate(
                "receipt_date",
                "19/08/2026",
            )
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(
            result.normalized_value,
            "2026-08-19",
        )
        self.assertEqual(
            result.rule,
            "dmy_four_digit_year",
        )

    # ------------------------------------------------------------------
    # 02. Ambiguous date
    # ------------------------------------------------------------------

    def test_02_ambiguous_date_is_not_guessed(self) -> None:
        candidate = make_candidate(
            "receipt_date",
            "08/09/2026",
        )

        normalized = normalize_receipt_date(
            candidate
        )

        decision = decide_review(
            "receipt_date",
            [candidate],
            normalized,
        )

        self.assertFalse(
            normalized.succeeded
        )
        self.assertEqual(
            decision.review_reasons,
            ("AMBIGUOUS_FORMAT",),
        )

    # ------------------------------------------------------------------
    # 03. Two-digit year review
    # ------------------------------------------------------------------

    def test_03_two_digit_year_requires_review(self) -> None:
        candidate = make_candidate(
            "receipt_date",
            "08/09/26",
            raw_text=(
                "NGÀY GIAO DỊCH: 08/09/26"
            ),
            positive=("ngày giao dịch",),
        )

        normalized = normalize_receipt_date(
            candidate
        )

        decision = decide_review(
            "receipt_date",
            [candidate],
            normalized,
        )

        self.assertIsNone(
            normalized.normalized_value
        )
        self.assertEqual(
            decision.review_reasons,
            ("UNSUPPORTED_TWO_DIGIT_YEAR",),
        )

    # ------------------------------------------------------------------
    # 04. VND normalization
    # ------------------------------------------------------------------

    def test_04_vnd_amount_normalizes_to_integer(self) -> None:
        result = normalize_total_amount(
            make_candidate(
                "total_amount",
                "325.000 VND",
            )
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(
            result.normalized_value,
            325000,
        )
        self.assertIsInstance(
            result.normalized_value,
            int,
        )

    # ------------------------------------------------------------------
    # 05. Ambiguous / corrupted OCR money
    # ------------------------------------------------------------------

    def test_05_ambiguous_ocr_money_is_not_repaired(self) -> None:
        candidate = make_candidate(
            "total_amount",
            "325.OOO VND",
        )

        normalized = normalize_total_amount(
            candidate
        )

        decision = decide_review(
            "total_amount",
            [candidate],
            normalized,
        )

        self.assertFalse(
            normalized.succeeded
        )
        self.assertEqual(
            decision.review_reasons,
            ("NORMALIZATION_FAILED",),
        )

    # ------------------------------------------------------------------
    # 06. Invoice leading zero
    # ------------------------------------------------------------------

    def test_06_invoice_id_preserves_leading_zero(self) -> None:
        result = normalize_invoice_id(
            make_candidate(
                "invoice_id",
                "001238",
            )
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(
            result.normalized_value,
            "001238",
        )
        self.assertIsInstance(
            result.normalized_value,
            str,
        )
    def test_06a_accentless_invoice_label_is_extracted(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "SO HD: 001238",
                    0,
                    0.30,
                ),
            ]
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        field = result["fields"]["invoice_id"]

        self.assertEqual(
            field["predicted_value"],
            "001238",
        )
        self.assertEqual(
            field["normalized_value"],
            "001238",
        )
        self.assertEqual(
            field["source_block_ids"],
            ["b0"],
        )
    def test_06b_transaction_id_is_available_as_typed_fallback(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "MA GIAO DICH: TXN-0099",
                    0,
                    0.30,
                ),
            ]
        )

        candidates = generate_invoice_id_candidates(
            ocr
        )

        self.assertEqual(len(candidates), 1)

        candidate = candidates[0]

        self.assertEqual(
            candidate.predicted_value,
            "TXN-0099",
        )
        self.assertEqual(
            candidate.candidate_role,
            "fallback",
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        self.assertEqual(
            result["fields"]["invoice_id"][
                "normalized_value"
            ],
            "TXN-0099",
        )

    def test_06c_split_transaction_label_is_typed_fallback(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "MA GIAO DICH",
                    0,
                    0.30,
                ),
                make_block(
                    "b1",
                    "TXN-0099",
                    1,
                    0.34,
                ),
            ]
        )

        candidates = generate_invoice_id_candidates(
            ocr
        )

        self.assertEqual(len(candidates), 1)

        candidate = candidates[0]

        self.assertEqual(
            candidate.predicted_value,
            "TXN-0099",
        )
        self.assertEqual(
            candidate.candidate_role,
            "fallback",
        )
        self.assertEqual(
            candidate.source_block_ids,
            ("b0", "b1"),
        )
        self.assertEqual(
            candidate.matched_patterns,
            ("split_fallback_label_value",),
        )

    def test_06d_primary_invoice_id_outranks_fallback(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "MA GIAO DICH: TXN-9999",
                    0,
                    0.50,
                    confidence=0.99,
                ),
                make_block(
                    "b1",
                    "SO HD: 001238",
                    1,
                    0.90,
                    confidence=0.10,
                ),
            ]
        )

        candidates = generate_invoice_id_candidates(
            ocr
        )

        self.assertEqual(
            {
                candidate.candidate_role
                for candidate in candidates
            },
            {"primary", "fallback"},
        )

        ranked = rank_candidates(candidates)

        self.assertEqual(
            ranked[0].candidate_role,
            "primary",
        )
        self.assertEqual(
            ranked[0].predicted_value,
            "001238",
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        self.assertEqual(
            result["fields"]["invoice_id"][
                "predicted_value"
            ],
            "001238",
        )
    # ------------------------------------------------------------------
    # 07. Multiple total candidates
    # ------------------------------------------------------------------

    def test_07_multiple_close_total_candidates_require_review(
        self,
    ) -> None:
        first = make_candidate(
            "total_amount",
            "325000",
            score=0.90,
        )

        second = make_candidate(
            "total_amount",
            "320000",
            score=0.85,
            source_block_ids=("b1",),
        )

        normalized = NormalizationResult(
            normalized_value=325000,
            rule="vnd_plain_integer",
            version="normalization-v0.1",
        )

        decision = decide_review(
            "total_amount",
            [first, second],
            normalized,
        )

        self.assertTrue(
            decision.machine_needs_review
        )
        self.assertIn(
            "MULTIPLE_CANDIDATES",
            decision.review_reasons,
        )

    def test_07a_candidate_score_is_positive_weighted_sum(
        self,
    ) -> None:
        candidate = Candidate(
            field_name="invoice_id",
            predicted_value="001238",
            source_block_ids=("b0",),
            raw_text="SO HD: 001238",
            matched_positive_keywords=("số hđ",),
            matched_negative_keywords=(),
            pattern_score=0.8,
            context_score=0.6,
            layout_score=0.4,
            ocr_score=1.0,
            final_score=0.0,
        )

        scored = score_candidate(
            candidate,
            {
                "pattern": 0.25,
                "context": 0.25,
                "layout": 0.25,
                "ocr_quality": 0.25,
            },
        )

        self.assertAlmostEqual(
            scored.final_score,
            0.7,
        )

    # ------------------------------------------------------------------
    # 08. Do not choose numerically largest amount
    # ------------------------------------------------------------------

    def test_08_total_ranking_does_not_use_largest_amount_shortcut(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "TỔNG THANH TOÁN",
                    0,
                    0.65,
                ),
                make_block(
                    "b1",
                    "325.000 VND",
                    1,
                    0.70,
                ),
                make_block(
                    "b2",
                    "TIỀN KHÁCH ĐƯA",
                    2,
                    0.75,
                ),
                make_block(
                    "b3",
                    "500.000 VND",
                    3,
                    0.80,
                ),
            ]
        )

        candidates = (
            generate_total_amount_candidates(
                ocr
            )
        )

        ranked = rank_candidates(
            candidates
        )

        self.assertGreaterEqual(
            len(ranked),
            2,
        )

        self.assertEqual(
            ranked[0].predicted_value,
            "325.000 VND",
        )

    def test_08a_negative_amount_preserves_sign_during_generation(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "TỔNG THANH TOÁN: -325.000 VND",
                    0,
                    0.65,
                ),
            ]
        )

        candidates = generate_total_amount_candidates(
            ocr
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0].predicted_value,
            "-325.000 VND",
        )

    def test_08b_negative_amount_requires_pipeline_review(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "TỔNG THANH TOÁN: -325.000 VND",
                    0,
                    0.65,
                ),
            ]
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        field = result["fields"]["total_amount"]

        self.assertEqual(
            field["predicted_value"],
            "-325.000 VND",
        )
        self.assertIsNone(
            field["normalized_value"]
        )
        self.assertTrue(
            field["machine_needs_review"]
        )
        self.assertIn(
            "NEGATIVE_AMOUNT",
            field["review_reasons"],
        )

    def test_08c_unsupported_currency_requires_pipeline_review(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "TỔNG THANH TOÁN: 325.000 USD",
                    0,
                    0.65,
                ),
            ]
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        field = result["fields"]["total_amount"]

        self.assertEqual(
            field["predicted_value"],
            "325.000 USD",
        )
        self.assertIsNone(
            field["normalized_value"]
        )
        self.assertTrue(
            field["machine_needs_review"]
        )
        self.assertIn(
            "UNSUPPORTED_CURRENCY",
            field["review_reasons"],
        )

    def test_08d_plain_integer_amount_is_extracted_in_positive_context(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "TỔNG THANH TOÁN: 325000",
                    0,
                    0.65,
                ),
            ]
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        field = result["fields"]["total_amount"]

        self.assertEqual(
            field["predicted_value"],
            "325000",
        )
        self.assertEqual(
            field["normalized_value"],
            325000,
        )
    def test_08e_corrupted_money_reaches_normalization_review(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "TỔNG THANH TOÁN: 325.OOO VND",
                    0,
                    0.65,
                ),
            ]
        )

        candidates = generate_total_amount_candidates(
            ocr
        )

        self.assertEqual(len(candidates), 1)

        candidate = candidates[0]

        self.assertEqual(
            candidate.matched_patterns,
            ("corrupted_amount_with_currency",),
        )
        self.assertEqual(
            candidate.ambiguity_indicators,
            ("digit_letter_confusion",),
        )
        self.assertEqual(
            candidate.normalization_indicators,
            (
                "currency_marker_present",
                "grouping_separator_present",
            ),
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        field = result["fields"]["total_amount"]

        self.assertEqual(
            field["predicted_value"],
            "325.OOO VND",
        )
        self.assertIsNone(
            field["normalized_value"]
        )
        self.assertTrue(
            field["machine_needs_review"]
        )
        self.assertIn(
            "NORMALIZATION_FAILED",
            field["review_reasons"],
        )
    # ------------------------------------------------------------------
    # 09. Multi-block merchant address
    # ------------------------------------------------------------------

    def test_09_multi_block_address_is_preserved_and_normalized(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "ĐỊA CHỈ: 12 NGUYỄN TRÃI",
                    0,
                    0.10,
                ),
                make_block(
                    "b1",
                    "PHƯỜNG 3, QUẬN 5",
                    1,
                    0.15,
                ),
                make_block(
                    "b2",
                    "TP. HỒ CHÍ MINH",
                    2,
                    0.20,
                ),
            ]
        )

        candidates = (
            generate_merchant_address_candidates(
                ocr
            )
        )

        self.assertEqual(
            len(candidates),
            1,
        )

        candidate = candidates[0]

        self.assertEqual(
            candidate.source_block_ids,
            ("b0", "b1", "b2"),
        )

        result = normalize_merchant_address(
            candidate
        )

        self.assertEqual(
            result.normalized_value,
            (
                "12 NGUYỄN TRÃI, "
                "PHƯỜNG 3, QUẬN 5, "
                "TP. HỒ CHÍ MINH"
            ),
        )

    # ------------------------------------------------------------------
    # 10. Source block IDs
    # ------------------------------------------------------------------

    def test_10_pipeline_emits_source_block_ids(self) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "SỐ HĐ: 001238",
                    0,
                    0.30,
                ),
            ]
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        field = result["fields"][
            "invoice_id"
        ]

        self.assertEqual(
            field["source_block_ids"],
            ["b0"],
        )

    # ------------------------------------------------------------------
    # 11. raw_text in OCR reading order
    # ------------------------------------------------------------------

    def test_11_raw_text_uses_ocr_reading_order(self) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "ĐỊA CHỈ: 12 NGUYỄN TRÃI",
                    0,
                    0.10,
                ),
                make_block(
                    "b1",
                    "PHƯỜNG 3, QUẬN 5",
                    1,
                    0.15,
                ),
                make_block(
                    "b2",
                    "TP. HỒ CHÍ MINH",
                    2,
                    0.20,
                ),
            ]
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        field = result["fields"][
            "merchant_address"
        ]

        self.assertEqual(
            field["raw_text"],
            (
                "ĐỊA CHỈ: 12 NGUYỄN TRÃI\n"
                "PHƯỜNG 3, QUẬN 5\n"
                "TP. HỒ CHÍ MINH"
            ),
        )

    # ------------------------------------------------------------------
    # 12. No-candidate review
    # ------------------------------------------------------------------

    def test_12_no_candidate_becomes_unknown_review(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "CẢM ƠN QUÝ KHÁCH",
                    0,
                    0.90,
                ),
            ]
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        field = result["fields"][
            "total_amount"
        ]

        self.assertEqual(
            field["value_status"],
            "UNKNOWN",
        )
        self.assertIsNone(
            field["predicted_value"]
        )
        self.assertIsNone(
            field["normalized_value"]
        )
        self.assertTrue(
            field["machine_needs_review"]
        )
        self.assertEqual(
            field["review_reasons"],
            ["NO_CANDIDATE"],
        )

    # ------------------------------------------------------------------
    # 13. Normalization-failure review
    # ------------------------------------------------------------------

    def test_13_normalization_failure_requires_review(
        self,
    ) -> None:
        candidate = make_candidate(
            "total_amount",
            "325.OOO VND",
        )

        normalized = normalize_total_amount(
            candidate
        )

        decision = decide_review(
            "total_amount",
            [candidate],
            normalized,
        )

        self.assertTrue(
            decision.machine_needs_review
        )
        self.assertEqual(
            decision.review_reasons,
            ("NORMALIZATION_FAILED",),
        )

    # ------------------------------------------------------------------
    # 14. Schema validation
    # ------------------------------------------------------------------

    def test_14_pipeline_output_validates_against_kie_schema(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "HIGHLANDS COFFEE",
                    0,
                    0.05,
                ),
                make_block(
                    "b1",
                    "SỐ HĐ: 001238",
                    1,
                    0.30,
                ),
                make_block(
                    "b2",
                    "NGÀY GIAO DỊCH: 19/08/2026",
                    2,
                    0.40,
                ),
                make_block(
                    "b3",
                    "TỔNG THANH TOÁN",
                    3,
                    0.70,
                ),
                make_block(
                    "b4",
                    "325.000 VND",
                    4,
                    0.76,
                ),
            ]
        )

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        # Must not raise.
        validate_kie_result(
            result
        )

        self.assertEqual(
            set(result["fields"]),
            {
                "merchant_name",
                "receipt_date",
                "total_amount",
                "invoice_id",
                "merchant_address",
            },
        )

    # ------------------------------------------------------------------
    # 15. Determinism except runtime metadata
    # ------------------------------------------------------------------

    def test_15_pipeline_is_semantically_deterministic(
        self,
    ) -> None:
        ocr = make_ocr(
            [
                make_block(
                    "b0",
                    "HIGHLANDS COFFEE",
                    0,
                    0.05,
                ),
                make_block(
                    "b1",
                    "SỐ HĐ: 001238",
                    1,
                    0.30,
                ),
                make_block(
                    "b2",
                    "NGÀY GIAO DỊCH: 19/08/2026",
                    2,
                    0.40,
                ),
                make_block(
                    "b3",
                    "TỔNG THANH TOÁN",
                    3,
                    0.70,
                ),
                make_block(
                    "b4",
                    "325.000 VND",
                    4,
                    0.76,
                ),
            ]
        )

        first = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        second = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        self.assertEqual(
            first["fields"],
            second["fields"],
        )

        self.assertEqual(
            first["extractor"],
            second["extractor"],
        )

        self.assertEqual(
            first["receipt_id"],
            second["receipt_id"],
        )

        self.assertEqual(
            first["kie_run_id"],
            second["kie_run_id"],
        )

        self.assertEqual(
            first["source_ocr_run_id"],
            second["source_ocr_run_id"],
        )

    # ------------------------------------------------------------------
    # 16. Caller-supplied immutable run linkage
    # ------------------------------------------------------------------

    def test_16_pipeline_preserves_supplied_run_ids(
        self,
    ) -> None:
        ocr = make_ocr([])

        result = run_kie(
            ocr,
            kie_run_id=KIE_RUN_ID,
        )

        self.assertEqual(
            result["receipt_id"],
            RECEIPT_ID,
        )

        self.assertEqual(
            result["source_ocr_run_id"],
            OCR_RUN_ID,
        )

        self.assertEqual(
            result["kie_run_id"],
            str(KIE_RUN_ID),
        )


if __name__ == "__main__":
    unittest.main()
