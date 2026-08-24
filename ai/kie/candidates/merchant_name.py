from __future__ import annotations

import re
import unicodedata
from typing import Any

from ai.kie.candidates.metadata import unreadable_source_indicators
from ai.kie.models import Candidate

from dataclasses import replace

from ai.kie.config import load_baseline_config
from ai.kie.ranking.features import (
    merchant_name_context_score,
    merchant_name_layout_score,
    merchant_name_pattern_score,
)
from ai.kie.ranking.scorer import score_candidate
# ---------------------------------------------------------------------------
# Keyword seed
# ---------------------------------------------------------------------------

POSITIVE_KEYWORDS = (
    "cửa hàng",
    "siêu thị",
    "minimart",
    "mart",
    "nhà thuốc",
    "hiệu thuốc",
    "quán",
    "nhà hàng",
    "cà phê",
    "coffee",
    "chi nhánh",
    "công ty",
    "cty",
    "doanh nghiệp",
)


NEGATIVE_KEYWORDS = (
    "khách hàng",
    "người mua",
    "thu ngân",
    "nhân viên",
    "ngân hàng",
    "ví điện tử",
    "đơn vị vận chuyển",
    "mã số thuế",
    "mst",
    "điện thoại",
    "hotline",
    "website",
    "email",
)


# Exact generic document titles that must not become merchant candidates.
GENERIC_DOCUMENT_TITLES = (
    "hóa đơn bán hàng",
    "phiếu thanh toán",
    "hóa đơn",
    "phiếu tính tiền",
    "bill",
    "receipt",
    "invoice",
)


# ---------------------------------------------------------------------------
# Candidate patterns
# ---------------------------------------------------------------------------

LEGAL_ENTITY_PATTERN = re.compile(
    r"\b(?:"
    r"CÔNG\s+TY"
    r"|CTY"
    r"|DOANH\s+NGHIỆP"
    r")\b",
    flags=re.IGNORECASE | re.UNICODE,
)


EXPLICIT_STORE_PATTERN = re.compile(
    r"\b(?:"
    r"CỬA\s+HÀNG"
    r"|SIÊU\s+THỊ"
    r"|NHÀ\s+THUỐC"
    r"|CHI\s+NHÁNH"
    r")\b",
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


MOSTLY_NUMERIC_PATTERN = re.compile(
    r"^[\d\s.,:/#()\-+]+$",
    flags=re.UNICODE,
)


HEADER_MAX_CENTER_Y = 0.30


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


def _normalized_text(
    text: str,
) -> str:
    return " ".join(
        text.casefold().split()
    )


def _block_center_y(
    block: dict[str, Any],
) -> float:
    polygon = block["polygon"]

    return sum(
        float(point["y"])
        for point in polygon
    ) / len(polygon)


def _contains_letter(
    text: str,
) -> bool:
    return any(
        character.isalpha()
        for character in text
    )


def _is_obvious_non_merchant(
    text: str,
    negative_keywords: tuple[str, ...],
) -> bool:
    stripped = text.strip()

    if not stripped:
        return True

    normalized = _normalized_text(stripped)

    # Important fix from Step 6D7:
    # generic receipt/document titles are not merchant names.
    if normalized in GENERIC_DOCUMENT_TITLES:
        return True

    if negative_keywords:
        return True

    if EMAIL_PATTERN.search(stripped):
        return True

    if WEBSITE_PATTERN.search(stripped):
        return True

    if PHONE_PATTERN.fullmatch(stripped):
        return True

    if MOSTLY_NUMERIC_PATTERN.fullmatch(stripped):
        return True

    if not _contains_letter(stripped):
        return True

    return False


# ---------------------------------------------------------------------------
# Candidate generator
# ---------------------------------------------------------------------------

def generate_merchant_name_candidates(
    ocr_result: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> list[Candidate]:
    """
    Generate and score merchant_name candidates from a canonical OCRResult.

    Candidate sources:
    1. Explicit merchant/store/legal entity text.
    2. Readable text near the receipt header.

    This function:
    - generates merchant-name candidates;
    - computes deterministic ranking features;
    - computes heuristic final_score.

    It does NOT:
    - normalize merchant names;
    - resolve brand vs legal entity;
    - resolve ambiguity;
    - infer names from external knowledge;
    - produce final field status/review decisions.
    """

    if config is None:
        config = load_baseline_config()

    weights = config["weights"]

    blocks = sorted(
        ocr_result["blocks"],
        key=lambda block: block["reading_order"],
    )

    candidates: list[Candidate] = []

    for block in blocks:
        text = block["text"].strip()

        if not text:
            continue

        positive_keywords = _matched_keywords(
            text,
            POSITIVE_KEYWORDS,
        )

        negative_keywords = _matched_keywords(
            text,
            NEGATIVE_KEYWORDS,
        )

        if _is_obvious_non_merchant(
            text,
            negative_keywords,
        ):
            continue

        legal_entity_match = LEGAL_ENTITY_PATTERN.search(text)
        explicit_store_match = EXPLICIT_STORE_PATTERN.search(text)
        explicit_match = bool(
            legal_entity_match or explicit_store_match
        )

        center_y = _block_center_y(block)

        is_header_candidate = (
            center_y <= HEADER_MAX_CENTER_Y
        )

        if not explicit_match and not is_header_candidate:
            continue

        if legal_entity_match is not None:
            matched_patterns = ("legal_entity",)
        elif explicit_store_match is not None:
            matched_patterns = ("explicit_store",)
        else:
            matched_patterns = ("header_text",)

        ambiguity_indicators = unreadable_source_indicators(text)

        if not explicit_match and not positive_keywords:
            ambiguity_indicators += ("source_role_unclear",)

        normalization_indicators: list[str] = []

        if unicodedata.normalize("NFC", text) != text:
            normalization_indicators.append("unicode_nfc_required")

        if re.search(r"\s{2,}", text):
            normalization_indicators.append("whitespace_collapse_required")

        candidate = Candidate(
            field_name="merchant_name",
            predicted_value=text,
            source_block_ids=(
                block["block_id"],
            ),
            raw_text=text,
            matched_positive_keywords=positive_keywords,
            matched_negative_keywords=negative_keywords,
            pattern_score=0.0,
            context_score=0.0,
            layout_score=0.0,
            ocr_score=float(block["confidence"]),
            final_score=0.0,
            matched_patterns=matched_patterns,
            ambiguity_indicators=ambiguity_indicators,
            normalization_indicators=tuple(
                normalization_indicators
            ),
        )

        candidate = replace(
            candidate,
            pattern_score=merchant_name_pattern_score(
                candidate,
                config,
            ),
            context_score=merchant_name_context_score(
                candidate,
                config,
            ),
            layout_score=merchant_name_layout_score(
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
