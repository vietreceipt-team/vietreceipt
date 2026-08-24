from __future__ import annotations

import re
import unicodedata

from ai.kie.models import Candidate, NormalizationResult


NORMALIZATION_VERSION = "normalization-v0.1"

RULE_IDENTITY_STRING = "identity_string"
RULE_NFC_WHITESPACE_NORMALIZED = "nfc_whitespace_normalized"


SAFE_SEPARATOR_CHARACTERS = {
    ".",
    "_",
    "/",
    "-",
    " ",
}


def _failed_result() -> NormalizationResult:
    return NormalizationResult(
        normalized_value=None,
        rule=None,
        version=None,
    )


def _is_safe_invoice_id(
    value: str,
) -> bool:
    """
    Accept letters/digits plus a small set of meaningful separators.

    Unicode letters/digits are allowed. Leading zeros are preserved.
    """

    if not value:
        return False

    if not value[0].isalnum():
        return False

    return all(
        character.isalnum()
        or character in SAFE_SEPARATOR_CHARACTERS
        for character in value
    )


def normalize_invoice_id(
    candidate: Candidate,
) -> NormalizationResult:
    """
    Deterministically normalize an invoice_id candidate.

    Safe operations:
    - Unicode NFC normalization;
    - trim leading/trailing whitespace;
    - collapse repeated whitespace to one ASCII space;
    - preserve leading zeros;
    - preserve meaningful separators such as "-", "/", "_", ".".

    Examples:
        "001238"
            -> "001238"

        "HD-000123"
            -> "HD-000123"

        "  HD   000123  "
            -> "HD 000123"

    This function does NOT:
    - convert the identifier to an integer;
    - remove meaningful separators;
    - change letter case;
    - repair OCR substitutions;
    - implement transaction/reference fallback semantics;
    - assign value_status or review reasons.
    """

    if candidate.field_name != "invoice_id":
        raise ValueError(
            "normalize_invoice_id requires an invoice_id candidate"
        )

    original = candidate.predicted_value

    if not original:
        return _failed_result()

    nfc_value = unicodedata.normalize(
        "NFC",
        original,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        nfc_value.strip(),
    )

    if not normalized:
        return _failed_result()

    if not _is_safe_invoice_id(
        normalized
    ):
        return _failed_result()

    rule = (
        RULE_IDENTITY_STRING
        if normalized == original
        else RULE_NFC_WHITESPACE_NORMALIZED
    )

    return NormalizationResult(
        normalized_value=normalized,
        rule=rule,
        version=NORMALIZATION_VERSION,
    )