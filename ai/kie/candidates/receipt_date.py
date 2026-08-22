from __future__ import annotations

import re
from typing import Any

from ai.kie.models import Candidate
from dataclasses import replace

from ai.kie.config import load_baseline_config
from ai.kie.ranking.features import (
    receipt_date_context_score,
    receipt_date_layout_score,
    receipt_date_pattern_score,
)
from ai.kie.ranking.scorer import score_candidate


# Candidate-level numeric date with a four-digit year.
#
# Important:
# Candidate generation does NOT decide whether the first component is
# day or month. Therefore both first and second components may range
# from 1..31 here.
#
# Calendar validity and DD/MM vs MM/DD resolution belong to the
# normalization stage.
FOUR_DIGIT_DATE_PATTERN = re.compile(
    r"\b(?:0?[1-9]|[12]\d|3[01])[\/.-]"
    r"(?:0?[1-9]|[12]\d|3[01])[\/.-]"
    r"(?:19|20)\d{2}\b",
    flags=re.UNICODE,
)


# Two-digit year is still allowed to become a candidate.
#
# VietReceipt v1 must NOT infer the century later.
# Example:
#   14/08/20
# must remain ambiguous during normalization/review.
TWO_DIGIT_YEAR_DATE_PATTERN = re.compile(
    r"\b(?:0?[1-9]|[12]\d|3[01])[\/.-]"
    r"(?:0?[1-9]|[12]\d|3[01])[\/.-]"
    r"\d{2}\b",
    flags=re.UNICODE,
)


# ISO-style date candidate.
ISO_DATE_PATTERN = re.compile(
    r"\b(?:19|20)\d{2}-"
    r"(?:0[1-9]|1[0-2])-"
    r"(?:0[1-9]|[12]\d|3[01])\b",
    flags=re.UNICODE,
)


POSITIVE_KEYWORDS = (
    "ngày bán",
    "ngày giao dịch",
    "ngày thanh toán",
    "thời gian",
    "datetime",
    "date",
    "transaction date",
)


NEGATIVE_KEYWORDS = (
    "hạn sử dụng",
    "ngày hết hạn",
    "hạn đổi trả",
    "ngày sinh",
    "valid thru",
    "expiry",
)


def _matched_keywords(
    text: str,
    keywords: tuple[str, ...],
) -> tuple[str, ...]:
    """
    Return all configured keywords found in text.

    Matching is case-insensitive via casefold().
    """

    lowered = text.casefold()

    return tuple(
        keyword
        for keyword in keywords
        if keyword.casefold() in lowered
    )


def _select_context_blocks(
    blocks: list[dict[str, Any]],
    index: int,
) -> list[dict[str, Any]]:
    """
    Select OCR evidence blocks for a date candidate.

    Rules:
    1. If the current block already contains semantic context,
       use only the current block.
    2. If the current block is unlabeled but the previous block
       contains a date-related label/context, use previous + current.
    3. Otherwise use only the current block.

    This prevents context leakage between unrelated dates while still
    supporting layouts such as:

        Ngày giao dịch
        18/08/2026
    """

    current = blocks[index]

    current_positive = _matched_keywords(
        current["text"],
        POSITIVE_KEYWORDS,
    )

    current_negative = _matched_keywords(
        current["text"],
        NEGATIVE_KEYWORDS,
    )

    # Current block already explains its semantic role.
    if current_positive or current_negative:
        return [current]

    if index == 0:
        return [current]

    previous = blocks[index - 1]

    previous_positive = _matched_keywords(
        previous["text"],
        POSITIVE_KEYWORDS,
    )

    previous_negative = _matched_keywords(
        previous["text"],
        NEGATIVE_KEYWORDS,
    )

    # Previous block is useful only when it acts as a semantic label
    # for an otherwise unlabeled date value.
    if previous_positive or previous_negative:
        return [previous, current]

    return [current]


def generate_receipt_date_candidates(
    ocr_result: dict[str, Any],
) -> list[Candidate]:
    """
    Generate receipt_date candidates from a canonical OCRResult.

    This function:
    - generates date candidates;
    - computes deterministic ranking features;
    - computes the baseline heuristic final score.

    It does NOT:
    - normalize dates to YYYY-MM-DD;
    - infer two-digit years;
    - decide DD/MM versus MM/DD;
    - resolve ambiguity;
    - produce the final KIE field.

    Those responsibilities belong to later normalization and
    review-policy stages.
    """

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
            POSITIVE_KEYWORDS,
        )

        negative_keywords = _matched_keywords(
            context_text,
            NEGATIVE_KEYWORDS,
        )

        matches = []

        for pattern in (
            ISO_DATE_PATTERN,
            FOUR_DIGIT_DATE_PATTERN,
            TWO_DIGIT_YEAR_DATE_PATTERN,
        ):
            matches.extend(
                pattern.finditer(block["text"])
            )

        if not matches:
            continue

        source_block_ids = tuple(
            context_block["block_id"]
            for context_block in context_blocks
        )

        raw_text = "\n".join(
            context_block["text"]
            for context_block in context_blocks
        )

        for match in matches:
            candidate = Candidate(
                field_name="receipt_date",
                predicted_value=match.group(0).strip(),
                source_block_ids=source_block_ids,
                raw_text=raw_text,
                matched_positive_keywords=positive_keywords,
                matched_negative_keywords=negative_keywords,
                pattern_score=0.0,
                context_score=0.0,
                layout_score=0.0,
                ocr_score=float(block["confidence"]),
                final_score=0.0,
            )

            candidate = replace(
                candidate,
                pattern_score=receipt_date_pattern_score(
                    candidate,
                    config,
                ),
                context_score=receipt_date_context_score(
                    candidate,
                    config,
                ),
                layout_score=receipt_date_layout_score(
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