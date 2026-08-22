from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

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
    r"SỐ\s*(?:HÓA\s*ĐƠN|HĐ)"
    r"|MÃ\s*HÓA\s*ĐƠN"
    r"|INVOICE\s*(?:NO|NUMBER)"
    r"|RECEIPT\s*(?:NO|NUMBER)"
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


def _matched_keywords(
    text: str,
    keywords: tuple[str, ...],
) -> tuple[str, ...]:
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
        PRIMARY_POSITIVE_KEYWORDS,
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
        PRIMARY_POSITIVE_KEYWORDS,
    )

    if previous_positive:
        return [previous, current]

    return [current]


def generate_invoice_id_candidates(
    ocr_result: dict[str, Any],
) -> list[Candidate]:
    """
    Generate and score invoice_id candidates.

    Baseline v0.1 supports primary invoice/receipt identifiers only.

    This function:
    - generates candidates;
    - computes deterministic ranking features;
    - computes heuristic final_score.

    It does NOT:
    - normalize the identifier;
    - cast identifiers to integers;
    - remove leading zeroes;
    - resolve multiple candidates;
    - use transaction/reference IDs as fallback;
    - produce final KIE field status/review decisions.
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
            PRIMARY_POSITIVE_KEYWORDS,
        )

        negative_keywords = _matched_keywords(
            context_text,
            NEGATIVE_KEYWORDS,
        )

        predicted_value: str | None = None

        # Case 1:
        # Label and value are in the same OCR block.
        labeled_match = PRIMARY_INVOICE_ID_PATTERN.search(
            block["text"]
        )

        if labeled_match is not None:
            predicted_value = labeled_match.group(1).strip()

        # Case 2:
        # Previous block contains label, current block contains value.
        elif (
            len(context_blocks) == 2
            and positive_keywords
        ):
            value_text = block["text"].strip()

            if VALUE_ONLY_PATTERN.fullmatch(value_text):
                predicted_value = value_text

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