from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from ai.kie.config import load_baseline_config
from ai.kie.models import Candidate
from ai.kie.ranking.features import (
    total_amount_context_score,
    total_amount_layout_score,
    total_amount_pattern_score,
)
from ai.kie.ranking.scorer import score_candidate


CURRENCY_MARKER_PATTERN = (
    r"(?:VND|VNĐ|₫|Đ|USD|EUR|GBP|JPY|CNY|KRW|THB|SGD|AUD|CAD|[$€£¥])"
)


AMOUNT_WITH_CURRENCY_PATTERN = re.compile(
    rf"(?<![\w.,])-?"
    rf"(?:\d{{1,3}}(?:[.,\s]\d{{3}})+|\d+)\s*"
    rf"{CURRENCY_MARKER_PATTERN}(?!\w)",
    flags=re.IGNORECASE | re.UNICODE,
)


CORRUPTED_AMOUNT_WITH_CURRENCY_PATTERN = re.compile(
    rf"(?<![\w.,])-?"
    rf"(?=[\dO.,\s]*O)"
    rf"(?:[\dO]{{1,3}}(?:[.,\s][\dO]{{3}})+|[\dO]+)\s*"
    rf"{CURRENCY_MARKER_PATTERN}(?!\w)",
    flags=re.IGNORECASE | re.UNICODE,
)


AMOUNT_WITHOUT_CURRENCY_PATTERN = re.compile(
    r"(?<![\w.,])-?"
    r"(?:\d{1,3}(?:[.,\s]\d{3})+|\d+)"
    r"(?![\w.,])",
    flags=re.UNICODE,
)


POSITIVE_KEYWORDS = (
    "tổng tiền phải thanh toán",
    "tổng tiền thanh toán",
    "tổng thanh toán",
    "tiền khách trả",
    "phải trả",
    "thành tiền",
    "tổng cộng",
    "grand total",
    "amount due",
    "total due",
    "total",
)

NEGATIVE_KEYWORDS = (
    "tạm tính",
    "subtotal",
    "giảm giá",
    "discount",
    "tiền khách đưa",
    "cash received",
    "tiền trả lại",
    "change",
    "thuế",
    "vat",
    "đơn giá",
    "số lượng",
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


def _spans_overlap(
    first: tuple[int, int],
    second: tuple[int, int],
) -> bool:
    first_start, first_end = first
    second_start, second_end = second

    return first_start < second_end and second_start < first_end


def generate_total_amount_candidates(
    ocr_result: dict[str, Any],
) -> list[Candidate]:
    config = load_baseline_config()
    weights = config["weights"]

    blocks = sorted(
        ocr_result["blocks"],
        key=lambda block: block["reading_order"],
    )

    candidates: list[Candidate] = []

    for index, block in enumerate(blocks):
        context_blocks = []

        if index > 0:
            context_blocks.append(blocks[index - 1])

        context_blocks.append(block)

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

        # Explicit currency markers remain candidates even when their
        # currency is unsupported or their digits contain a conservative
        # OCR ambiguity. Normalization and review classify those cases.
        currency_matches = sorted(
            (
                list(
                    AMOUNT_WITH_CURRENCY_PATTERN.finditer(
                        block["text"]
                    )
                )
                + list(
                    CORRUPTED_AMOUNT_WITH_CURRENCY_PATTERN.finditer(
                        block["text"]
                    )
                )
            ),
            key=lambda match: match.span(),
        )

        # Amounts without an explicit currency marker are accepted only
        # when a positive total-amount context exists.
        contextual_matches = []

        if positive_keywords:
            contextual_matches = list(
                AMOUNT_WITHOUT_CURRENCY_PATTERN.finditer(
                    block["text"]
                )
            )

        # Avoid duplicate candidates such as "325.000 VND", for which
        # both the explicit-currency and contextual patterns see the
        # numeric span.
        non_duplicate_contextual_matches = [
            match
            for match in contextual_matches
            if not any(
                _spans_overlap(
                    match.span(),
                    currency_match.span(),
                )
                for currency_match in currency_matches
            )
        ]

        matches = sorted(
            (
                currency_matches
                + non_duplicate_contextual_matches
            ),
            key=lambda match: match.span(),
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
                field_name="total_amount",
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
                pattern_score=total_amount_pattern_score(
                    candidate,
                    config,
                ),
                context_score=total_amount_context_score(
                    candidate,
                    config,
                ),
                layout_score=total_amount_layout_score(
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
