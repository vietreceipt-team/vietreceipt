from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from ai.kie.models import Candidate


REQUIRED_WEIGHTS = (
    "pattern",
    "context",
    "layout",
    "ocr_quality",
)


CANDIDATE_ROLE_PRIORITY = {
    "primary": 2,
    "fallback": 1,
}


def score_candidate(
    candidate: Candidate,
    weights: Mapping[str, float],
) -> Candidate:
    missing = [
        name
        for name in REQUIRED_WEIGHTS
        if name not in weights
    ]

    if missing:
        raise ValueError(
            f"Missing ranking weights: {', '.join(missing)}"
        )

    weight_sum = sum(
        float(weights[name])
        for name in REQUIRED_WEIGHTS
    )

    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError(
            f"Ranking weights must sum to 1.0, got {weight_sum}"
        )

    final_score = (
        float(weights["pattern"]) * candidate.pattern_score
        + float(weights["context"]) * candidate.context_score
        + float(weights["layout"]) * candidate.layout_score
        + float(weights["ocr_quality"]) * candidate.ocr_score
    )

    final_score = max(0.0, min(1.0, final_score))

    return replace(
        candidate,
        final_score=final_score,
    )


def rank_candidates(
    candidates: list[Candidate],
) -> list[Candidate]:
    """
    Rank primary candidates before fallback candidates, then rank each
    role from highest to lowest final_score.

    Python's sort is stable, so equal keys preserve deterministic
    generation order.
    """

    return sorted(
        candidates,
        key=lambda candidate: (
            CANDIDATE_ROLE_PRIORITY.get(
                candidate.candidate_role,
                0,
            ),
            candidate.final_score,
        ),
        reverse=True,
    )


def candidate_margin(
    ranked_candidates: list[Candidate],
) -> float | None:
    """
    Return the score gap between top-1 and top-2 candidates.

    Returns None when fewer than two candidates exist.
    """

    if len(ranked_candidates) < 2:
        return None

    return (
        ranked_candidates[0].final_score
        - ranked_candidates[1].final_score
    )


def has_close_competitor(
    ranked_candidates: list[Candidate],
    *,
    margin_threshold: float,
) -> bool:
    """
    Return True when top-1 and top-2 are too close.

    This is a deterministic review heuristic,
    not a calibrated uncertainty estimate.
    """

    margin = candidate_margin(ranked_candidates)

    if margin is None:
        return False

    return margin < margin_threshold


def has_close_competitor_from_config(
    ranked_candidates: list[Candidate],
    config: Mapping[str, Any],
) -> bool:
    try:
        margin_threshold = float(
            config["review"]["close_candidate_margin"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Baseline config is missing "
            "review.close_candidate_margin"
        ) from exc

    return has_close_competitor(
        ranked_candidates,
        margin_threshold=margin_threshold,
    )
