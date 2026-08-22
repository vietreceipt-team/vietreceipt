from __future__ import annotations

import re
import unicodedata

from ai.kie.models import Candidate, NormalizationResult


NORMALIZATION_VERSION = "normalization-v0.1"

RULE_IDENTITY_STRING = "identity_string"
RULE_NFC_WHITESPACE_NORMALIZED = "nfc_whitespace_normalized"


def _failed_result() -> NormalizationResult:
    return NormalizationResult(
        normalized_value=None,
        rule=None,
        version=None,
    )


def normalize_merchant_name(
    candidate: Candidate,
) -> NormalizationResult:
    """
    Deterministically normalize a merchant_name candidate.

    Safe operations:
    - Unicode NFC normalization;
    - trim leading/trailing whitespace;
    - collapse repeated internal whitespace to one ASCII space.

    This function does NOT:
    - infer a brand from a legal entity;
    - expand abbreviations;
    - change case;
    - remove Vietnamese accents;
    - spell-correct OCR text;
    - use external merchant knowledge;
    - assign value_status or review reasons.
    """

    if candidate.field_name != "merchant_name":
        raise ValueError(
            "normalize_merchant_name requires a merchant_name candidate"
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