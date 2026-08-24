from __future__ import annotations

from typing import Any, Sequence

from ai.kie.models import Candidate, NormalizationResult
from ai.kie.ranking.scorer import candidate_margin


CONFIDENCE_VERSION = "heuristic-confidence-v0.2"


def candidate_confidence(
    candidate: Candidate,
) -> float:
    """
    Return the candidate ranking-score component clipped to [0, 1].

    This helper remains useful when inspecting candidates. Public field
    confidence is computed by ``field_confidence`` from ranking evidence,
    candidate separation, normalization certainty and ambiguity evidence.
    """

    return max(
        0.0,
        min(1.0, float(candidate.final_score)),
    )


def field_confidence(
    ranked_candidates: Sequence[Candidate],
    normalization_result: NormalizationResult | None,
    config: dict[str, Any],
) -> float:
    """
    Return deterministic, explainable W2 field confidence in [0, 1].

    Components are centralized in the versioned baseline config:

    - the best candidate's multi-feature ranking score;
    - separation from the next same-role candidate;
    - deterministic normalization success;
    - candidate ambiguity indicators.

    IMPORTANT:
    - This is a heuristic score.
    - It is NOT a calibrated probability.
    - It must NOT be interpreted as P(field_is_correct).
    - Calibration/AUROC/ECE/risk-coverage are evaluated later on held-out
      data before any selective verification policy is justified.
    """

    if not ranked_candidates:
        return 0.0

    confidence_config = config["confidence"]

    if confidence_config["version"] != CONFIDENCE_VERSION:
        raise ValueError(
            "Confidence config/version mismatch: "
            f"{confidence_config['version']!r}"
        )

    weights = confidence_config["weights"]
    best = ranked_candidates[0]
    margin = candidate_margin(list(ranked_candidates))

    if margin is None:
        separation_score = 1.0
    else:
        separation_score = min(
            1.0,
            margin
            / float(
                confidence_config["separation_full_margin"]
            ),
        )

    normalization_succeeded = bool(
        normalization_result is not None
        and normalization_result.succeeded
    )
    normalization_score = float(normalization_succeeded)

    if not best.ambiguity_indicators:
        ambiguity_score = 1.0
    elif normalization_succeeded:
        ambiguity_score = 0.5
    else:
        ambiguity_score = 0.0

    score = (
        float(weights["ranking_score"])
        * candidate_confidence(best)
        + float(weights["candidate_separation"])
        * separation_score
        + float(weights["normalization_certainty"])
        * normalization_score
        + float(weights["ambiguity_evidence"])
        * ambiguity_score
    )

    return round(max(0.0, min(1.0, score)), 6)
