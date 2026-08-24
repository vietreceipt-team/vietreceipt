from __future__ import annotations

import re

from ai.kie.models import Candidate, NormalizationResult


NORMALIZATION_VERSION = "normalization-v0.1"

RULE_VND_PLAIN_INTEGER = "vnd_plain_integer"
RULE_VND_GROUPED_INTEGER = "vnd_grouped_integer"


VND_MARKER_PATTERN = re.compile(
    r"(?:VND|VNĐ|₫|Đ)",
    flags=re.IGNORECASE | re.UNICODE,
)


PLAIN_INTEGER_PATTERN = re.compile(
    r"^\d+$",
    flags=re.UNICODE,
)


GROUPED_INTEGER_PATTERN = re.compile(
    r"^\d{1,3}(?P<sep>[., ])\d{3}"
    r"(?:(?P=sep)\d{3})*$",
    flags=re.UNICODE,
)


def _strip_vnd_marker(
    value: str,
) -> str | None:
    """
    Remove one optional VND marker from the beginning or end.

    Examples:
        "325.000 VND" -> "325.000"
        "VND 325.000" -> "325.000"
        "325000"      -> "325000"

    Returns None when the value contains unsupported or malformed
    currency-marker placement.
    """

    stripped = value.strip()

    suffix_match = re.fullmatch(
        rf"(.+?)\s*({VND_MARKER_PATTERN.pattern})",
        stripped,
        flags=re.IGNORECASE | re.UNICODE,
    )

    if suffix_match is not None:
        amount_part = suffix_match.group(1).strip()

        if VND_MARKER_PATTERN.search(amount_part):
            return None

        return amount_part

    prefix_match = re.fullmatch(
        rf"({VND_MARKER_PATTERN.pattern})\s*(.+)",
        stripped,
        flags=re.IGNORECASE | re.UNICODE,
    )

    if prefix_match is not None:
        amount_part = prefix_match.group(2).strip()

        if VND_MARKER_PATTERN.search(amount_part):
            return None

        return amount_part

    # If a currency-like VND marker still exists somewhere in the
    # value, its placement is not supported.
    if VND_MARKER_PATTERN.search(stripped):
        return None

    return stripped


def normalize_total_amount(
    candidate: Candidate,
) -> NormalizationResult:
    """
    Deterministically normalize a total_amount candidate to integer VND.

    Supported examples:
        "325000"       -> 325000
        "325.000"      -> 325000
        "325,000"      -> 325000
        "325 000"      -> 325000
        "325.000 VND"  -> 325000
        "VND 325.000"  -> 325000

    Unsafe or ambiguous representations return an unsuccessful
    NormalizationResult instead of guessing.

    This function does NOT:
    - decide value_status;
    - set machine_needs_review;
    - choose review reasons;
    - convert another currency to VND;
    - interpret decimal monetary values;
    - repair OCR substitutions.
    """

    if candidate.field_name != "total_amount":
        raise ValueError(
            "normalize_total_amount requires a total_amount candidate"
        )

    value = candidate.predicted_value.strip()

    if not value:
        return NormalizationResult(
            normalized_value=None,
            rule=None,
            version=None,
        )

    amount_text = _strip_vnd_marker(value)

    if amount_text is None:
        return NormalizationResult(
            normalized_value=None,
            rule=None,
            version=None,
        )

    # Normalize repeated whitespace without changing punctuation.
    amount_text = re.sub(
        r"\s+",
        " ",
        amount_text.strip(),
    )

    # Plain non-negative integer.
    if PLAIN_INTEGER_PATTERN.fullmatch(amount_text):
        return NormalizationResult(
            normalized_value=int(amount_text),
            rule=RULE_VND_PLAIN_INTEGER,
            version=NORMALIZATION_VERSION,
        )

    # Grouped integer. The regex requires one consistent separator
    # and groups of exactly three digits, preventing decimal-like
    # or mixed-separator interpretations.
    grouped_match = GROUPED_INTEGER_PATTERN.fullmatch(
        amount_text
    )

    if grouped_match is not None:
        separator = grouped_match.group("sep")

        digits = amount_text.replace(
            separator,
            "",
        )

        return NormalizationResult(
            normalized_value=int(digits),
            rule=RULE_VND_GROUPED_INTEGER,
            version=NORMALIZATION_VERSION,
        )

    return NormalizationResult(
        normalized_value=None,
        rule=None,
        version=None,
    )