from __future__ import annotations

import re
from typing import Any

from ai.kie.models import Candidate


# ===========================================================================
# TOTAL AMOUNT
# ===========================================================================

VND_MARKER_PATTERN = re.compile(
    r"(?:VND|VNĐ|₫|Đ)",
    flags=re.IGNORECASE | re.UNICODE,
)


GROUPED_AMOUNT_PATTERN = re.compile(
    r"^\s*\d{1,3}(?:[.,\s]\d{3})+\s*$",
    flags=re.UNICODE,
)


def _total_amount_features(
    config: dict[str, Any],
) -> dict[str, Any]:
    return config["features"]["total_amount"]


def total_amount_pattern_score(
    candidate: Candidate,
    config: dict[str, Any],
) -> float:
    feature_config = _total_amount_features(config)["pattern"]

    value = candidate.predicted_value.strip()

    if VND_MARKER_PATTERN.search(value):
        return float(
            feature_config["explicit_vnd_marker"]
        )

    if GROUPED_AMOUNT_PATTERN.fullmatch(value):
        return float(
            feature_config["grouped_without_currency"]
        )

    return float(
        feature_config["unsupported"]
    )


def total_amount_context_score(
    candidate: Candidate,
    config: dict[str, Any],
) -> float:
    feature_config = _total_amount_features(config)["context"]

    has_positive = bool(
        candidate.matched_positive_keywords
    )

    has_negative = bool(
        candidate.matched_negative_keywords
    )

    if has_positive and has_negative:
        return float(
            feature_config["conflicting"]
        )

    if has_positive:
        return float(
            feature_config["positive_only"]
        )

    if has_negative:
        return float(
            feature_config["negative_only"]
        )

    return float(
        feature_config["neutral"]
    )


def total_amount_layout_score(
    block: dict[str, Any],
    config: dict[str, Any],
) -> float:
    layout_config = _total_amount_features(config)["layout"]

    polygon = block["polygon"]

    if len(polygon) != 4:
        raise ValueError(
            "total_amount layout scoring requires a 4-point polygon"
        )

    center_y = sum(
        float(point["y"])
        for point in polygon
    ) / 4.0

    footer_start_y = float(
        layout_config["footer_start_y"]
    )

    middle_start_y = float(
        layout_config["middle_start_y"]
    )

    if center_y >= footer_start_y:
        return float(
            layout_config["footer_score"]
        )

    if center_y >= middle_start_y:
        return float(
            layout_config["middle_score"]
        )

    return float(
        layout_config["header_score"]
    )


# ===========================================================================
# RECEIPT DATE
# ===========================================================================

DATE_ISO_PATTERN = re.compile(
    r"^(?:19|20)\d{2}-"
    r"(?:0[1-9]|1[0-2])-"
    r"(?:0[1-9]|[12]\d|3[01])$",
    flags=re.UNICODE,
)


DATE_FOUR_DIGIT_YEAR_PATTERN = re.compile(
    r"^(?:0?[1-9]|[12]\d|3[01])[\/.-]"
    r"(?:0?[1-9]|[12]\d|3[01])[\/.-]"
    r"(?:19|20)\d{2}$",
    flags=re.UNICODE,
)


DATE_TWO_DIGIT_YEAR_PATTERN = re.compile(
    r"^(?:0?[1-9]|[12]\d|3[01])[\/.-]"
    r"(?:0?[1-9]|[12]\d|3[01])[\/.-]"
    r"\d{2}$",
    flags=re.UNICODE,
)


def _receipt_date_features(
    config: dict[str, Any],
) -> dict[str, Any]:
    return config["features"]["receipt_date"]


def receipt_date_pattern_score(
    candidate: Candidate,
    config: dict[str, Any],
) -> float:
    feature_config = _receipt_date_features(config)["pattern"]

    value = candidate.predicted_value.strip()

    if DATE_ISO_PATTERN.fullmatch(value):
        return float(
            feature_config["iso_date"]
        )

    if DATE_FOUR_DIGIT_YEAR_PATTERN.fullmatch(value):
        return float(
            feature_config["four_digit_year"]
        )

    if DATE_TWO_DIGIT_YEAR_PATTERN.fullmatch(value):
        return float(
            feature_config["two_digit_year"]
        )

    if "missing_date_component" in candidate.matched_patterns:
        return float(
            feature_config["missing_component"]
        )

    return float(
        feature_config["unsupported"]
    )


def receipt_date_context_score(
    candidate: Candidate,
    config: dict[str, Any],
) -> float:
    feature_config = _receipt_date_features(config)["context"]

    has_positive = bool(
        candidate.matched_positive_keywords
    )

    has_negative = bool(
        candidate.matched_negative_keywords
    )

    if has_positive and has_negative:
        return float(
            feature_config["conflicting"]
        )

    if has_positive:
        return float(
            feature_config["positive_only"]
        )

    if has_negative:
        return float(
            feature_config["negative_only"]
        )

    return float(
        feature_config["neutral"]
    )


def receipt_date_layout_score(
    block: dict[str, Any],
    config: dict[str, Any],
) -> float:
    feature_config = _receipt_date_features(config)["layout"]

    polygon = block["polygon"]

    center_y = sum(
        float(point["y"])
        for point in polygon
    ) / len(polygon)

    if center_y <= float(
        feature_config["header_end_y"]
    ):
        return float(
            feature_config["header_score"]
        )

    if center_y <= float(
        feature_config["body_end_y"]
    ):
        return float(
            feature_config["body_score"]
        )

    return float(
        feature_config["footer_score"]
    )


# ===========================================================================
# INVOICE ID
# ===========================================================================

def _invoice_id_features(
    config: dict[str, Any],
) -> dict[str, Any]:
    return config["features"]["invoice_id"]


def invoice_id_pattern_score(
    candidate: Candidate,
    config: dict[str, Any],
) -> float:
    feature_config = _invoice_id_features(config)["pattern"]
    source_block_count = len(
        candidate.source_block_ids
    )

    if candidate.candidate_role == "primary":
        if source_block_count == 1:
            return float(
                feature_config["labeled_primary_id"]
            )

        if source_block_count == 2:
            return float(
                feature_config["split_label_value"]
            )

    if candidate.candidate_role == "fallback":
        if source_block_count == 1:
            return float(
                feature_config["labeled_fallback_id"]
            )

        if source_block_count == 2:
            return float(
                feature_config[
                    "split_fallback_label_value"
                ]
            )

    return float(
        feature_config["unsupported"]
    )


def invoice_id_context_score(
    candidate: Candidate,
    config: dict[str, Any],
) -> float:
    feature_config = _invoice_id_features(config)["context"]

    has_positive = bool(
        candidate.matched_positive_keywords
    )

    has_negative = bool(
        candidate.matched_negative_keywords
    )

    if has_positive and has_negative:
        return float(
            feature_config["conflicting"]
        )

    if has_positive:
        return float(
            feature_config["positive_only"]
        )

    if has_negative:
        return float(
            feature_config["negative_only"]
        )

    return float(
        feature_config["neutral"]
    )


def invoice_id_layout_score(
    block: dict[str, Any],
    config: dict[str, Any],
) -> float:
    feature_config = _invoice_id_features(config)["layout"]

    polygon = block["polygon"]

    center_y = sum(
        float(point["y"])
        for point in polygon
    ) / len(polygon)

    if center_y <= float(
        feature_config["header_end_y"]
    ):
        return float(
            feature_config["header_score"]
        )

    if center_y <= float(
        feature_config["body_end_y"]
    ):
        return float(
            feature_config["body_score"]
        )

    return float(
        feature_config["footer_score"]
    )


# ===========================================================================
# MERCHANT NAME
# ===========================================================================

MERCHANT_LEGAL_ENTITY_PATTERN = re.compile(
    r"\b(?:"
    r"CÔNG\s+TY"
    r"|CTY"
    r"|DOANH\s+NGHIỆP"
    r")\b",
    flags=re.IGNORECASE | re.UNICODE,
)


MERCHANT_EXPLICIT_STORE_PATTERN = re.compile(
    r"\b(?:"
    r"CỬA\s+HÀNG"
    r"|SIÊU\s+THỊ"
    r"|NHÀ\s+THUỐC"
    r"|CHI\s+NHÁNH"
    r")\b",
    flags=re.IGNORECASE | re.UNICODE,
)


def _merchant_name_features(
    config: dict[str, Any],
) -> dict[str, Any]:
    return config["features"]["merchant_name"]


def merchant_name_pattern_score(
    candidate: Candidate,
    config: dict[str, Any],
) -> float:
    feature_config = _merchant_name_features(config)["pattern"]

    value = candidate.predicted_value.strip()

    if MERCHANT_LEGAL_ENTITY_PATTERN.search(value):
        return float(
            feature_config["legal_entity"]
        )

    if MERCHANT_EXPLICIT_STORE_PATTERN.search(value):
        return float(
            feature_config["explicit_store"]
        )

    if candidate.source_block_ids:
        return float(
            feature_config["header_text"]
        )

    return float(
        feature_config["unsupported"]
    )


def merchant_name_context_score(
    candidate: Candidate,
    config: dict[str, Any],
) -> float:
    feature_config = _merchant_name_features(config)["context"]

    has_positive = bool(
        candidate.matched_positive_keywords
    )

    has_negative = bool(
        candidate.matched_negative_keywords
    )

    if has_positive and has_negative:
        return float(
            feature_config["conflicting"]
        )

    if has_positive:
        return float(
            feature_config["positive_only"]
        )

    if has_negative:
        return float(
            feature_config["negative_only"]
        )

    return float(
        feature_config["neutral"]
    )


def merchant_name_layout_score(
    block: dict[str, Any],
    config: dict[str, Any],
) -> float:
    feature_config = _merchant_name_features(config)["layout"]

    polygon = block["polygon"]

    center_y = sum(
        float(point["y"])
        for point in polygon
    ) / len(polygon)

    if center_y <= float(
        feature_config["strong_header_end_y"]
    ):
        return float(
            feature_config["strong_header_score"]
        )

    if center_y <= float(
        feature_config["header_end_y"]
    ):
        return float(
            feature_config["header_score"]
        )

    return float(
        feature_config["body_score"]
    )


# ===========================================================================
# MERCHANT ADDRESS
# ===========================================================================

ADDRESS_LABEL_PATTERN = re.compile(
    r"(?:ĐỊA\s*CHỈ|ADDRESS)\s*[:#-]?",
    flags=re.IGNORECASE | re.UNICODE,
)


ADDRESS_ADMINISTRATIVE_PATTERN = re.compile(
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


ADDRESS_STREET_NUMBER_PATTERN = re.compile(
    r"^\s*"
    r"\d{1,5}[A-Z]?"
    r"(?:[/-]\d{1,5}[A-Z]?)?"
    r"\s+"
    r".*[A-ZÀ-Ỹ]",
    flags=re.IGNORECASE | re.UNICODE,
)


def _merchant_address_features(
    config: dict[str, Any],
) -> dict[str, Any]:
    return config["features"]["merchant_address"]


def merchant_address_pattern_score(
    candidate: Candidate,
    config: dict[str, Any],
) -> float:
    feature_config = _merchant_address_features(config)["pattern"]

    raw_text = candidate.raw_text.strip()
    value = candidate.predicted_value.strip()

    # raw_text preserves the original OCR label, while predicted_value
    # intentionally removes "ĐỊA CHỈ:" during candidate generation.
    if ADDRESS_LABEL_PATTERN.search(raw_text):
        return float(
            feature_config["labeled_address"]
        )

    if ADDRESS_ADMINISTRATIVE_PATTERN.search(value):
        return float(
            feature_config["administrative_context"]
        )

    if ADDRESS_STREET_NUMBER_PATTERN.search(value):
        return float(
            feature_config["street_number"]
        )

    return float(
        feature_config["unsupported"]
    )


def merchant_address_context_score(
    candidate: Candidate,
    config: dict[str, Any],
) -> float:
    feature_config = _merchant_address_features(config)["context"]

    has_positive = bool(
        candidate.matched_positive_keywords
    )

    has_negative = bool(
        candidate.matched_negative_keywords
    )

    if has_positive and has_negative:
        return float(
            feature_config["conflicting"]
        )

    if has_positive:
        return float(
            feature_config["positive_only"]
        )

    if has_negative:
        return float(
            feature_config["negative_only"]
        )

    return float(
        feature_config["neutral"]
    )


def merchant_address_layout_score(
    block: dict[str, Any],
    config: dict[str, Any],
) -> float:
    """
    Score address layout using the first source block of the candidate.

    For multi-block addresses, the first block is the anchor of the
    address candidate and determines its receipt-region feature.
    """

    feature_config = _merchant_address_features(config)["layout"]

    polygon = block["polygon"]

    center_y = sum(
        float(point["y"])
        for point in polygon
    ) / len(polygon)

    if center_y <= float(
        feature_config["header_end_y"]
    ):
        return float(
            feature_config["header_score"]
        )

    if center_y <= float(
        feature_config["body_end_y"]
    ):
        return float(
            feature_config["body_score"]
        )

    return float(
        feature_config["footer_score"]
    )
