from __future__ import annotations

import re
import unicodedata

from ai.kie.models import Candidate, NormalizationResult


NORMALIZATION_VERSION = "normalization-v0.1"

RULE_IDENTITY_STRING = "identity_string"
RULE_ADDRESS_LINES_JOINED = "address_lines_joined"
RULE_NFC_WHITESPACE_NORMALIZED = "nfc_whitespace_normalized"


def _failed_result() -> NormalizationResult:
    return NormalizationResult(
        normalized_value=None,
        rule=None,
        version=None,
    )


def _normalize_line(
    line: str,
) -> str:
    """
    Normalize whitespace inside one NFC-normalized OCR address line.

    No lexical, geographic, or abbreviation normalization is performed.
    """

    return re.sub(
        r"\s+",
        " ",
        line.strip(),
    )


def normalize_merchant_address(
    candidate: Candidate,
) -> NormalizationResult:
    """
    Deterministically normalize a merchant_address candidate.

    Safe operations:
    - Unicode NFC normalization;
    - trim leading/trailing whitespace;
    - collapse repeated whitespace within each line;
    - join multiple OCR address lines using ", ".

    Example:

        12 NGUYỄN TRÃI
        PHƯỜNG 3, QUẬN 5
        TP. HỒ CHÍ MINH

    becomes:

        12 NGUYỄN TRÃI, PHƯỜNG 3, QUẬN 5, TP. HỒ CHÍ MINH

    This function does NOT:
    - geocode;
    - expand administrative abbreviations;
    - infer missing administrative units;
    - spell-correct OCR text;
    - canonicalize street/place names;
    - choose branch vs headquarters;
    - assign value_status;
    - assign review reasons.
    """

    if candidate.field_name != "merchant_address":
        raise ValueError(
            "normalize_merchant_address requires a merchant_address candidate"
        )

    original = candidate.predicted_value

    if not original:
        return _failed_result()

    nfc_value = unicodedata.normalize(
        "NFC",
        original,
    )

    raw_lines = nfc_value.splitlines()

    normalized_lines: list[str] = []

    for line in raw_lines:
        normalized_line = _normalize_line(
            line
        )

        if normalized_line:
            normalized_lines.append(
                normalized_line
            )

    if not normalized_lines:
        return _failed_result()

    normalized = ", ".join(
        normalized_lines
    )

    if len(normalized_lines) > 1:
        rule = RULE_ADDRESS_LINES_JOINED

    elif normalized == original:
        rule = RULE_IDENTITY_STRING

    else:
        rule = RULE_NFC_WHITESPACE_NORMALIZED

    return NormalizationResult(
        normalized_value=normalized,
        rule=rule,
        version=NORMALIZATION_VERSION,
    )