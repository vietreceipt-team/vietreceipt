from __future__ import annotations

from ai.kie.models import Candidate


CONFIDENCE_VERSION = "heuristic-confidence-v0.1"


def candidate_confidence(
    candidate: Candidate,
) -> float:
    """
    Return the deterministic W2 heuristic confidence for a KIE candidate.

    In baseline v0.1, field confidence is the candidate's final ranking
    score, clipped to [0, 1].

    IMPORTANT:
    - This is a heuristic score.
    - It is NOT a calibrated probability.
    - It must NOT be interpreted as P(field_is_correct).
    - Calibration/AUROC/ECE/risk-coverage are evaluated later on held-out
      data before any selective verification policy is justified.
    """

    return max(
        0.0,
        min(1.0, float(candidate.final_score)),
    )