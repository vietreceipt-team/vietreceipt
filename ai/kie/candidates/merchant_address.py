from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from ai.kie.config import load_baseline_config
from ai.kie.models import Candidate
from ai.kie.ranking.features import (
    merchant_address_context_score,
    merchant_address_layout_score,
    merchant_address_pattern_score,
)
from ai.kie.ranking.scorer import score_candidate


# ---------------------------------------------------------------------------
# Keyword seed
# ---------------------------------------------------------------------------

POSITIVE_KEYWORDS = (
    "địa chỉ",
    "địa điểm",
    "chi nhánh",
    "address",
    "đường",
    "phố",
    "phường",
    "xã",
    "quận",
    "huyện",
    "tỉnh",
    "thành phố",
    "tp.",
)


NEGATIVE_KEYWORDS = (
    "địa chỉ khách hàng",
    "địa chỉ giao hàng",
    "shipping address",
    "billing address",
    "ngân hàng",
    "website",
    "email",
    "điện thoại",
    "hotline",
    "mã số thuế",
    "mst",
)


# ---------------------------------------------------------------------------
# Candidate patterns
# ---------------------------------------------------------------------------

LABELED_ADDRESS_PATTERN = re.compile(
    r"(?:ĐỊA\s*CHỈ|ADDRESS)"
    r"\s*[:#-]?\s*"
    r"(.{5,160})",
    flags=re.IGNORECASE | re.UNICODE,
)


# Important:
# Do not use trailing \b after "TP." because "." is a non-word
# character and the following whitespace is also non-word.
ADMINISTRATIVE_PATTERN = re.compile(
    r"(?<!\w)(?:"
    r"ĐƯỜNG"
    r"|PHỐ"
    r"|PHƯỜNG"
    r"|XÃ"
    r"|QUẬN"
    r"|HUYỆN"
    r"|TỈNH"
    r"|THÀNH\s+PHỐ"
    r"|TP\."
    r")(?!\w)",
    flags=re.IGNORECASE | re.UNICODE,
)


# Supports unlabeled address lines such as:
#   12 NGUYỄN TRÃI
#   123A LÊ LỢI
#   12/3 NGUYỄN HUỆ
STREET_NUMBER_PATTERN = re.compile(
    r"^\s*"
    r"\d{1,5}[A-Z]?"
    r"(?:[/-]\d{1,5}[A-Z]?)?"
    r"\s+"
    r".*[A-ZÀ-Ỹ]",
    flags=re.IGNORECASE | re.UNICODE,
)


EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    flags=re.IGNORECASE | re.UNICODE,
)


WEBSITE_PATTERN = re.compile(
    r"(?:https?://|www\.)\S+",
    flags=re.IGNORECASE | re.UNICODE,
)


PHONE_PATTERN = re.compile(
    r"(?:\+?84|0)\s*(?:\d[\s.-]*){8,10}\d",
    flags=re.IGNORECASE | re.UNICODE,
)


DATE_PATTERN = re.compile(
    r"^\s*(?:"
    r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
    r"|"
    r"\d{4}-\d{1,2}-\d{1,2}"
    r")\s*$",
    flags=re.UNICODE,
)


AMOUNT_PATTERN = re.compile(
    r"^\s*[\d.,\s]+\s*(?:VND|VNĐ|₫|Đ)?\s*$",
    flags=re.IGNORECASE | re.UNICODE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _is_obvious_non_address(
    text: str,
    negative_keywords: tuple[str, ...],
) -> bool:
    stripped = text.strip()

    if not stripped:
        return True

    if negative_keywords:
        return True

    if EMAIL_PATTERN.search(stripped):
        return True

    if WEBSITE_PATTERN.search(stripped):
        return True

    if PHONE_PATTERN.fullmatch(stripped):
        return True

    if DATE_PATTERN.fullmatch(stripped):
        return True

    if AMOUNT_PATTERN.fullmatch(stripped):
        return True

    return False


def _looks_like_address_line(
    text: str,
) -> bool:
    """
    Broad deterministic address-line detector.

    Candidate generation remains permissive.
    Final address selection belongs to ranking/review.
    """

    stripped = text.strip()

    if LABELED_ADDRESS_PATTERN.search(stripped):
        return True

    if ADMINISTRATIVE_PATTERN.search(stripped):
        return True

    if STREET_NUMBER_PATTERN.search(stripped):
        return True

    return False


def _looks_like_continuation(
    text: str,
) -> bool:
    """
    Determine whether the next OCR block can continue an address.
    """

    stripped = text.strip()

    if ADMINISTRATIVE_PATTERN.search(stripped):
        return True

    if STREET_NUMBER_PATTERN.search(stripped):
        return True

    return False


def _candidate_value_from_blocks(
    source_blocks: list[dict[str, Any]],
) -> str:
    """
    Build the pre-normalization candidate value.

    For a labeled first line:

        ĐỊA CHỈ: 12 NGUYỄN TRÃI
        PHƯỜNG 3, QUẬN 5

    predicted_value becomes:

        12 NGUYỄN TRÃI
        PHƯỜNG 3, QUẬN 5

    while raw_text still preserves the exact OCR evidence including
    the "ĐỊA CHỈ:" label.

    Joining with comma-space belongs to normalization later.
    """

    first_text = source_blocks[0]["text"].strip()

    labeled_match = LABELED_ADDRESS_PATTERN.search(
        first_text
    )

    values: list[str] = []

    if labeled_match is not None:
        values.append(
            labeled_match.group(1).strip()
        )
    else:
        values.append(first_text)

    for block in source_blocks[1:]:
        values.append(
            block["text"].strip()
        )

    return "\n".join(values)


# ---------------------------------------------------------------------------
# Candidate generator + deterministic feature scoring
# ---------------------------------------------------------------------------

def generate_merchant_address_candidates(
    ocr_result: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> list[Candidate]:
    """
    Generate and score merchant_address candidates from canonical OCRResult.

    Supports:
    - explicitly labeled addresses;
    - Vietnamese administrative context;
    - unlabeled street-number lines;
    - consecutive multi-block addresses.

    This function:
    - generates address candidates;
    - preserves exact OCR evidence;
    - computes deterministic ranking features;
    - computes heuristic final_score.

    It does NOT:
    - choose among multiple addresses;
    - decide branch vs headquarters;
    - join lines with commas;
    - expand abbreviations;
    - spell-correct place names;
    - geocode;
    - add missing location information;
    - produce final status/review decisions.
    """

    if config is None:
        config = load_baseline_config()

    weights = config["weights"]

    blocks = sorted(
        ocr_result["blocks"],
        key=lambda block: block["reading_order"],
    )

    candidates: list[Candidate] = []

    index = 0

    while index < len(blocks):
        block = blocks[index]
        text = block["text"].strip()

        negative_keywords = _matched_keywords(
            text,
            NEGATIVE_KEYWORDS,
        )

        if _is_obvious_non_address(
            text,
            negative_keywords,
        ):
            index += 1
            continue

        if not _looks_like_address_line(text):
            index += 1
            continue

        source_blocks = [block]

        # Add consecutive address continuation blocks.
        next_index = index + 1

        while next_index < len(blocks):
            next_block = blocks[next_index]
            next_text = next_block["text"].strip()

            next_negative = _matched_keywords(
                next_text,
                NEGATIVE_KEYWORDS,
            )

            if _is_obvious_non_address(
                next_text,
                next_negative,
            ):
                break

            if not _looks_like_continuation(next_text):
                break

            source_blocks.append(next_block)
            next_index += 1

        # raw_text preserves exact OCR evidence in reading order.
        raw_text = "\n".join(
            source_block["text"]
            for source_block in source_blocks
        )

        # predicted_value excludes an explicit "ĐỊA CHỈ:" label,
        # but otherwise remains close to OCR text.
        predicted_value = _candidate_value_from_blocks(
            source_blocks
        )

        positive_keywords = _matched_keywords(
            raw_text,
            POSITIVE_KEYWORDS,
        )

        negative_keywords = _matched_keywords(
            raw_text,
            NEGATIVE_KEYWORDS,
        )

        # OCR-quality aggregation across all evidence blocks.
        ocr_score = sum(
            float(source_block["confidence"])
            for source_block in source_blocks
        ) / len(source_blocks)

        candidate = Candidate(
            field_name="merchant_address",
            predicted_value=predicted_value,
            source_block_ids=tuple(
                source_block["block_id"]
                for source_block in source_blocks
            ),
            raw_text=raw_text,
            matched_positive_keywords=positive_keywords,
            matched_negative_keywords=negative_keywords,
            pattern_score=0.0,
            context_score=0.0,
            layout_score=0.0,
            ocr_score=ocr_score,
            final_score=0.0,
        )

        candidate = replace(
            candidate,
            pattern_score=merchant_address_pattern_score(
                candidate,
                config,
            ),
            context_score=merchant_address_context_score(
                candidate,
                config,
            ),
            # The first source block is the deterministic layout anchor
            # for a multi-block address candidate.
            layout_score=merchant_address_layout_score(
                source_blocks[0],
                config,
            ),
        )

        candidate = score_candidate(
            candidate,
            weights,
        )

        candidates.append(candidate)

        index = next_index

    return candidates