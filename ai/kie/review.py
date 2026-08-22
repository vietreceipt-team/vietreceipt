from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from ai.kie.confidence import candidate_confidence
from ai.kie.config import load_baseline_config
from ai.kie.models import Candidate, NormalizationResult
from ai.kie.ranking.scorer import (
    has_close_competitor_from_config,
    rank_candidates,
)


@dataclass(frozen=True)
class ReviewDecision:
    """
    Machine-only review decision for one KIE field.

    This object does NOT contain human corrections and does NOT imply
    calibrated probability or automatic verification.
    """

    machine_needs_review: bool
    review_reasons: tuple[str, ...]
    review_policy_version: str | None


# ---------------------------------------------------------------------------
# Field-specific normalization-failure patterns
# ---------------------------------------------------------------------------

TWO_DIGIT_YEAR_PATTERN = re.compile(
    r"^\s*"
    r"\d{1,2}[./-]"
    r"\d{1,2}[./-]"
    r"\d{2}"
    r"\s*$",
    flags=re.UNICODE,
)


FOUR_DIGIT_DATE_PATTERN = re.compile(
    r"^\s*"
    r"(?P<first>\d{1,2})"
    r"(?P<sep>[./-])"
    r"(?P<second>\d{1,2})"
    r"(?P=sep)"
    r"(?P<year>\d{4})"
    r"\s*$",
    flags=re.UNICODE,
)


NON_VND_CURRENCY_PATTERN = re.compile(
    r"(?:"
    r"\bUSD\b"
    r"|\bEUR\b"
    r"|\bGBP\b"
    r"|\bJPY\b"
    r"|\bCNY\b"
    r"|\bRMB\b"
    r"|\bTHB\b"
    r"|\bSGD\b"
    r"|\bAUD\b"
    r"|\bCAD\b"
    r"|[$€£¥]"
    r")",
    flags=re.IGNORECASE | re.UNICODE,
)


NEGATIVE_AMOUNT_PATTERN = re.compile(
    r"^\s*-\s*\d",
    flags=re.UNICODE,
)


# ---------------------------------------------------------------------------
# Field-specific semantic reasons
# ---------------------------------------------------------------------------

def _receipt_date_failure_reason(
    value: str,
) -> str | None:
    """
    Classify known deterministic receipt-date normalization failures.

    Does not infer locale or repair malformed dates.
    """

    stripped = value.strip()

    if TWO_DIGIT_YEAR_PATTERN.fullmatch(stripped):
        return "UNSUPPORTED_TWO_DIGIT_YEAR"

    match = FOUR_DIGIT_DATE_PATTERN.fullmatch(
        stripped
    )

    if match is None:
        return None

    first = int(
        match.group("first")
    )

    second = int(
        match.group("second")
    )

    # Both positions are valid month numbers, so DD/MM and MM/DD
    # cannot be distinguished safely without locale inference.
    if (
        1 <= first <= 12
        and 1 <= second <= 12
    ):
        return "AMBIGUOUS_FORMAT"

    return None


def _total_amount_failure_reason(
    value: str,
) -> str | None:
    """
    Classify known deterministic total-amount normalization failures.
    """

    stripped = value.strip()

    if NEGATIVE_AMOUNT_PATTERN.search(
        stripped
    ):
        return "NEGATIVE_AMOUNT"

    if NON_VND_CURRENCY_PATTERN.search(
        stripped
    ):
        return "UNSUPPORTED_CURRENCY"

    return None


def _normalization_failure_reason(
    field_name: str,
    candidate: Candidate,
) -> str | None:
    """
    Return a field-specific semantic reason when normalization failure
    can be classified safely.

    None means the failure remains generic and should use
    NORMALIZATION_FAILED.
    """

    value = candidate.predicted_value

    if field_name == "receipt_date":
        return _receipt_date_failure_reason(
            value
        )

    if field_name == "total_amount":
        return _total_amount_failure_reason(
            value
        )

    return None


# ---------------------------------------------------------------------------
# Review policy
# ---------------------------------------------------------------------------

def decide_review(
    field_name: str,
    candidates: Sequence[Candidate],
    normalization_result: NormalizationResult | None,
    *,
    config: dict[str, Any] | None = None,
) -> ReviewDecision:
    """
    Apply deterministic W2 review policy to one field.

    Generic review triggers:
    - no candidate;
    - low heuristic confidence;
    - close competing candidate;
    - normalization failure.

    Known normalization failures receive a more specific semantic
    review reason where classification is deterministic.
    """

    if config is None:
        config = load_baseline_config()

    review_config = config["review"]

    policy_version = str(
        review_config["policy_version"]
    )

    thresholds = review_config[
        "low_confidence_thresholds"
    ]

    if field_name not in thresholds:
        raise ValueError(
            f"Missing review threshold for field: {field_name}"
        )

    # ------------------------------------------------------------------
    # No candidate
    # ------------------------------------------------------------------

    if not candidates:
        return ReviewDecision(
            machine_needs_review=True,
            review_reasons=("NO_CANDIDATE",),
            review_policy_version=policy_version,
        )

    ranked = rank_candidates(
        list(candidates)
    )

    best = ranked[0]

    reasons: list[str] = []

    # ------------------------------------------------------------------
    # Low heuristic confidence
    # ------------------------------------------------------------------

    confidence = candidate_confidence(
        best
    )

    threshold = float(
        thresholds[field_name]
    )

    if confidence < threshold:
        reasons.append(
            "LOW_CONFIDENCE"
        )

    # ------------------------------------------------------------------
    # Multiple close candidates
    # ------------------------------------------------------------------

    if has_close_competitor_from_config(
        ranked,
        config,
    ):
        reasons.append(
            "MULTIPLE_CANDIDATES"
        )

    # ------------------------------------------------------------------
    # Normalization failure
    # ------------------------------------------------------------------

    if (
        normalization_result is None
        or not normalization_result.succeeded
    ):
        specific_reason = (
            _normalization_failure_reason(
                field_name,
                best,
            )
        )

        if specific_reason is not None:
            reasons.append(
                specific_reason
            )
        else:
            reasons.append(
                "NORMALIZATION_FAILED"
            )

    # ------------------------------------------------------------------
    # Final deterministic decision
    # ------------------------------------------------------------------

    if reasons:
        return ReviewDecision(
            machine_needs_review=True,
            review_reasons=tuple(reasons),
            review_policy_version=policy_version,
        )

    return ReviewDecision(
        machine_needs_review=False,
        review_reasons=(),
        review_policy_version=None,
    )