from __future__ import annotations

import re
from datetime import date

from ai.kie.models import Candidate, NormalizationResult


NORMALIZATION_VERSION = "normalization-v0.1"

RULE_ISO_DATE = "iso_date"
RULE_DMY_FOUR_DIGIT_YEAR = "dmy_four_digit_year"
RULE_MDY_FOUR_DIGIT_YEAR = "mdy_four_digit_year"
RULE_DMY_VI_TRANSACTION_LABEL = "dmy_vi_transaction_label"


ISO_DATE_PATTERN = re.compile(
    r"^(?P<year>\d{4})-"
    r"(?P<month>\d{1,2})-"
    r"(?P<day>\d{1,2})$",
    flags=re.UNICODE,
)


FOUR_DIGIT_YEAR_PATTERN = re.compile(
    r"^(?P<first>\d{1,2})"
    r"(?P<sep>[./-])"
    r"(?P<second>\d{1,2})"
    r"(?P=sep)"
    r"(?P<year>\d{4})$",
    flags=re.UNICODE,
)


TWO_DIGIT_YEAR_PATTERN = re.compile(
    r"^\d{1,2}[./-]\d{1,2}[./-]\d{2}$",
    flags=re.UNICODE,
)


# Vietnamese transaction-date labels provide deterministic DD/MM/YYYY
# locale evidence under the VietReceipt v1 field specification.
#
# Explicit transaction labels:
#   NGÀY BÁN
#   NGÀY GIAO DỊCH
#   NGÀY THANH TOÁN
#
# Generic "NGÀY" is accepted only in a label-like position such as:
#   NGÀY: 08/09/2026
#   NGÀY 08/09/2026
#
# Negative-role candidate context is checked separately before this
# evidence can be used.
VI_TRANSACTION_DATE_LABEL_PATTERN = re.compile(
    r"(?:"
    r"(?<!\w)NGÀY\s+BÁN(?!\w)"
    r"|(?<!\w)NGÀY\s+GIAO\s+DỊCH(?!\w)"
    r"|(?<!\w)NGÀY\s+THANH\s+TOÁN(?!\w)"
    r"|(?:^|\n)\s*NGÀY\s*(?=[:#-]|\d)"
    r")",
    flags=re.IGNORECASE | re.UNICODE,
)


def _failed_result() -> NormalizationResult:
    return NormalizationResult(
        normalized_value=None,
        rule=None,
        version=None,
    )


def _build_iso_date(
    year: int,
    month: int,
    day: int,
) -> str | None:
    """
    Validate a calendar date and return canonical YYYY-MM-DD.

    Invalid dates such as 31/02/2026 return None.
    """

    try:
        parsed = date(
            year=year,
            month=month,
            day=day,
        )
    except ValueError:
        return None

    return parsed.isoformat()


def _has_vietnamese_transaction_date_label(
    candidate: Candidate,
) -> bool:
    """
    Return True only when OCR evidence provides safe Vietnamese
    transaction-date locale evidence.

    A candidate carrying negative semantic context must never use a
    generic Vietnamese date label to force DD/MM/YYYY interpretation.
    """

    if candidate.matched_negative_keywords:
        return False

    return (
        VI_TRANSACTION_DATE_LABEL_PATTERN.search(
            candidate.raw_text
        )
        is not None
    )


def normalize_receipt_date(
    candidate: Candidate,
) -> NormalizationResult:
    """
    Deterministically normalize a receipt_date candidate.

    Safe cases:
        2026-08-19
            -> 2026-08-19

        19/08/2026
            -> 2026-08-19
            because only DD/MM is calendar-valid

        08/19/2026
            -> 2026-08-19
            because only MM/DD is calendar-valid

        raw_text = "NGÀY GIAO DỊCH: 08/09/2026"
        predicted_value = "08/09/2026"
            -> 2026-09-08
            because Vietnamese transaction-label evidence permits
            deterministic DD/MM/YYYY interpretation.

    Ambiguous without locale evidence:
        08/09/2026
            -> None

    Two-digit years remain unsupported:
        19/08/26
            -> None

    This function does NOT:
    - infer locale without OCR evidence;
    - infer two-digit years;
    - repair OCR errors;
    - assign value_status;
    - assign review reasons.
    """

    if candidate.field_name != "receipt_date":
        raise ValueError(
            "normalize_receipt_date requires a receipt_date candidate"
        )

    value = candidate.predicted_value.strip()

    if not value:
        return _failed_result()

    # ------------------------------------------------------------------
    # Canonical ISO input
    # ------------------------------------------------------------------

    iso_match = ISO_DATE_PATTERN.fullmatch(
        value
    )

    if iso_match is not None:
        normalized = _build_iso_date(
            year=int(
                iso_match.group("year")
            ),
            month=int(
                iso_match.group("month")
            ),
            day=int(
                iso_match.group("day")
            ),
        )

        if normalized is None:
            return _failed_result()

        return NormalizationResult(
            normalized_value=normalized,
            rule=RULE_ISO_DATE,
            version=NORMALIZATION_VERSION,
        )

    # ------------------------------------------------------------------
    # Explicitly reject two-digit years.
    # ------------------------------------------------------------------

    if TWO_DIGIT_YEAR_PATTERN.fullmatch(
        value
    ):
        return _failed_result()

    # ------------------------------------------------------------------
    # Four-digit year with numeric first/second components.
    # ------------------------------------------------------------------

    match = FOUR_DIGIT_YEAR_PATTERN.fullmatch(
        value
    )

    if match is None:
        return _failed_result()

    first = int(
        match.group("first")
    )

    second = int(
        match.group("second")
    )

    year = int(
        match.group("year")
    )

    # ------------------------------------------------------------------
    # Ambiguous numeric order: both components can be months.
    #
    # Example:
    #   08/09/2026
    #
    # Without locale evidence:
    #   ambiguous -> fail normalization.
    #
    # With a Vietnamese transaction-date label:
    #   deterministic DD/MM/YYYY is allowed by contract v1.
    # ------------------------------------------------------------------

    if (
        1 <= first <= 12
        and 1 <= second <= 12
    ):
        if not _has_vietnamese_transaction_date_label(
            candidate
        ):
            return _failed_result()

        normalized = _build_iso_date(
            year=year,
            month=second,
            day=first,
        )

        if normalized is None:
            return _failed_result()

        return NormalizationResult(
            normalized_value=normalized,
            rule=RULE_DMY_VI_TRANSACTION_LABEL,
            version=NORMALIZATION_VERSION,
        )

    # ------------------------------------------------------------------
    # first > 12 means first can only be the day.
    #
    #   19/08/2026 -> DD/MM/YYYY
    # ------------------------------------------------------------------

    if (
        first > 12
        and 1 <= second <= 12
    ):
        normalized = _build_iso_date(
            year=year,
            month=second,
            day=first,
        )

        if normalized is None:
            return _failed_result()

        return NormalizationResult(
            normalized_value=normalized,
            rule=RULE_DMY_FOUR_DIGIT_YEAR,
            version=NORMALIZATION_VERSION,
        )

    # ------------------------------------------------------------------
    # second > 12 means second can only be the day.
    #
    #   08/19/2026 -> MM/DD/YYYY
    # ------------------------------------------------------------------

    if (
        second > 12
        and 1 <= first <= 12
    ):
        normalized = _build_iso_date(
            year=year,
            month=first,
            day=second,
        )

        if normalized is None:
            return _failed_result()

        return NormalizationResult(
            normalized_value=normalized,
            rule=RULE_MDY_FOUR_DIGIT_YEAR,
            version=NORMALIZATION_VERSION,
        )

    return _failed_result()