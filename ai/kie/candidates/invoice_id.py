from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from typing import Any

from ai.kie.candidates.metadata import unreadable_source_indicators
from ai.kie.config import load_baseline_config
from ai.kie.models import Candidate
from ai.kie.ranking.features import (
    invoice_id_context_score,
    invoice_id_layout_score,
    invoice_id_pattern_score,
)
from ai.kie.ranking.scorer import score_candidate


# Baseline v0.1 intentionally supports only primary invoice/receipt IDs.
#
# Transaction/reference IDs are excluded for now because the canonical
# KIE schema has no `id_type` field required by the field specification
# for fallback identifiers.
PRIMARY_POSITIVE_KEYWORDS = (
    "số hóa đơn",
    "số hđ",
    "mã hóa đơn",
    "invoice no",
    "invoice number",
    "receipt no",
    "receipt number",
)

FALLBACK_POSITIVE_KEYWORDS = (
    "mã giao dịch",
    "số giao dịch",
    "mã gd",
    "số gd",
    "mã tham chiếu",
    "số tham chiếu",
    "transaction id",
    "transaction no",
    "transaction number",
    "reference id",
    "reference no",
    "reference number",
    "ref id",
    "ref no",
)


ALL_POSITIVE_KEYWORDS = (
    PRIMARY_POSITIVE_KEYWORDS
    + FALLBACK_POSITIVE_KEYWORDS
)

NEGATIVE_KEYWORDS = (
    "mã số thuế",
    "tax code",
    "mst",
    "mã sản phẩm",
    "barcode",
    "số điện thoại",
    "terminal id",
    "pos id",
    "batch no",
    "authorization code",
    "mã khách hàng",
)


# Label and invoice ID are in the same OCR block.
#
# Examples:
#   SỐ HĐ: 001238
#   MÃ HÓA ĐƠN: HD-000123
#   Invoice No: INV/000456
#   Receipt Number # RCP-0099
#
# Capture group 1 is the candidate value.
PRIMARY_INVOICE_ID_PATTERN = re.compile(
    r"(?:"
    r"SO\s*(?:HOA\s*DON|HD)"
    r"|MA\s*HOA\s*DON"
    r"|INVOICE\s*(?:NO|NUMBER)"
    r"|RECEIPT\s*(?:NO|NUMBER)"
    r")"
    r"\s*[:#-]?\s*"
    r"([A-Z0-9][A-Z0-9._/-]*)",
    flags=re.IGNORECASE | re.UNICODE,
)

FALLBACK_INVOICE_ID_PATTERN = re.compile(
    r"(?:"
    r"(?:MA|SO)\s*"
    r"(?:GIAO\s*DICH|GD|THAM\s*CHIEU)"
    r"|TRANSACTION\s*(?:ID|NO|NUMBER)"
    r"|REFERENCE\s*(?:ID|NO|NUMBER)"
    r"|REF\s*(?:ID|NO|NUMBER)"
    r")"
    r"\s*[:#-]?\s*"
    r"([A-Z0-9][A-Z0-9._/-]*)",
    flags=re.IGNORECASE | re.UNICODE,
)

# Used when label and value are split across two OCR blocks.
#
# Example:
#   block_0: SỐ HĐ
#   block_1: HD-000123
VALUE_ONLY_PATTERN = re.compile(
    r"^[A-Z0-9][A-Z0-9._/-]*$",
    flags=re.IGNORECASE | re.UNICODE,
)

def _fold_vietnamese_diacritics(
    text: str,
) -> str:
    decomposed = unicodedata.normalize(
        "NFD",
        text,
    )

    without_combining_marks = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )

    return (
        without_combining_marks
        .replace("Đ", "D")
        .replace("đ", "d")
    )


def _matched_keywords(
    text: str,
    keywords: tuple[str, ...],
) -> tuple[str, ...]:
    folded_text = (
        _fold_vietnamese_diacritics(text)
        .casefold()
    )

    return tuple(
        keyword
        for keyword in keywords
        if (
            _fold_vietnamese_diacritics(keyword)
            .casefold()
            in folded_text
        )
    )


def _select_context_blocks(
    blocks: list[dict[str, Any]],
    index: int,
) -> list[dict[str, Any]]:
    """
    Select OCR evidence blocks for an invoice ID.

    Rules:
    1. If current block already carries primary invoice or negative
       semantics, use only current block.
    2. If current block is unlabeled and previous block contains a
       primary invoice label, use previous + current.
    3. Otherwise use only current block.
    """

    current = blocks[index]

    current_positive = _matched_keywords(
        current["text"],
        ALL_POSITIVE_KEYWORDS,
    )

    current_negative = _matched_keywords(
        current["text"],
        NEGATIVE_KEYWORDS,
    )

    if current_positive or current_negative:
        return [current]

    if index == 0:
        return [current]

    previous = blocks[index - 1]

    previous_positive = _matched_keywords(
        previous["text"],
        ALL_POSITIVE_KEYWORDS,
    )

    if previous_positive:
        return [previous, current]

    return [current]


def generate_invoice_id_candidates(
    ocr_result: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> list[Candidate]:
    """
    Generate and score invoice_id candidates.

    Baseline v0.1 prefers primary invoice/receipt identifiers and exposes
    transaction/reference identifiers as typed internal fallbacks.

    This function:
    - generates candidates;
    - computes deterministic ranking features;
    - computes heuristic final_score.

    It does NOT:
    - normalize the identifier;
    - cast identifiers to integers;
    - remove leading zeroes;
    - resolve multiple candidates;
    - produce final KIE field status/review decisions.
    """

    if config is None:
        config = load_baseline_config()

    weights = config["weights"]

    blocks = sorted(
        ocr_result["blocks"],
        key=lambda block: block["reading_order"],
    )

    candidates: list[Candidate] = []

    for index, block in enumerate(blocks):
        context_blocks = _select_context_blocks(
            blocks,
            index,
        )

        context_text = "\n".join(
            context_block["text"]
            for context_block in context_blocks
        )

        positive_keywords = _matched_keywords(
            context_text,
            ALL_POSITIVE_KEYWORDS,
        )

        negative_keywords = _matched_keywords(
            context_text,
            NEGATIVE_KEYWORDS,
        )

        predicted_value: str | None = None
        candidate_role = "primary"
        matched_patterns: tuple[str, ...] = ()

        folded_block_text = (
            _fold_vietnamese_diacritics(
                block["text"]
            )
        )

        primary_match = PRIMARY_INVOICE_ID_PATTERN.search(
            folded_block_text
        )

        if primary_match is not None:
            predicted_value = (
                primary_match.group(1).strip()
            )
            matched_patterns = (
                "labeled_primary_id",
            )

        else:
            fallback_match = (
                FALLBACK_INVOICE_ID_PATTERN.search(
                    folded_block_text
                )
            )

            if fallback_match is not None:
                predicted_value = (
                    fallback_match.group(1).strip()
                )
                candidate_role = "fallback"
                matched_patterns = (
                    "labeled_fallback_id",
                )

            elif (
                len(context_blocks) == 2
                and positive_keywords
            ):
                value_text = block["text"].strip()

                if VALUE_ONLY_PATTERN.fullmatch(
                    value_text
                ):
                    previous_text = context_blocks[
                        0
                    ]["text"]

                    previous_primary_keywords = (
                        _matched_keywords(
                            previous_text,
                            PRIMARY_POSITIVE_KEYWORDS,
                        )
                    )

                    previous_fallback_keywords = (
                        _matched_keywords(
                            previous_text,
                            FALLBACK_POSITIVE_KEYWORDS,
                        )
                    )

                    if previous_primary_keywords:
                        predicted_value = value_text
                        candidate_role = "primary"
                        matched_patterns = (
                            "split_label_value",
                        )

                    elif previous_fallback_keywords:
                        predicted_value = value_text
                        candidate_role = "fallback"
                        matched_patterns = (
                            "split_fallback_label_value",
                        )

        if predicted_value is None:
            continue

        source_block_ids = tuple(
            context_block["block_id"]
            for context_block in context_blocks
        )

        raw_text = "\n".join(
            context_block["text"]
            for context_block in context_blocks
        )

        normalization_indicators = (
            ("leading_zero_preserved",)
            if predicted_value.startswith("0")
            else ("identifier_string_preserved",)
        )

        candidate = Candidate(
            field_name="invoice_id",
            predicted_value=predicted_value,
            source_block_ids=source_block_ids,
            raw_text=raw_text,
            matched_positive_keywords=positive_keywords,
            matched_negative_keywords=negative_keywords,
            pattern_score=0.0,
            context_score=0.0,
            layout_score=0.0,
            ocr_score=float(block["confidence"]),
            final_score=0.0,
            candidate_role=candidate_role,
            matched_patterns=matched_patterns,
            ambiguity_indicators=(
                unreadable_source_indicators(raw_text)
            ),
            normalization_indicators=(
                normalization_indicators
            ),
        )

        candidate = replace(
            candidate,
            pattern_score=invoice_id_pattern_score(
                candidate,
                config,
            ),
            context_score=invoice_id_context_score(
                candidate,
                config,
            ),
            layout_score=invoice_id_layout_score(
                block,
                config,
            ),
        )

        candidate = score_candidate(
            candidate,
            weights,
        )

        candidates.append(candidate)

    return candidates
