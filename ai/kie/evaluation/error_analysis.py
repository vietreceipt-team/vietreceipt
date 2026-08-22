from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from ai.kie.evaluation.metrics import EvaluationPair
from ai.kie.pipeline import FIELD_NAMES


ERROR_TAXONOMY_DEFINITIONS = {
    "OCR_OMISSION": (
        "Oracle OCR produces the correct field while Real OCR provides "
        "no candidate value"
    ),
    "OCR_SUBSTITUTION": (
        "Oracle OCR produces the correct field while Real OCR produces "
        "a different value or status"
    ),
    "CANDIDATE_GENERATION_FAILURE": (
        "KIE produces no candidate from Oracle OCR for a gold PRESENT field"
    ),
    "CANDIDATE_RANKING_FAILURE": (
        "Oracle OCR contains usable evidence but KIE selects an incorrect "
        "candidate or status"
    ),
    "NORMALIZATION_FAILURE": (
        "KIE selects a candidate from Oracle OCR but deterministic "
        "normalization fails"
    ),
    "AMBIGUITY": (
        "Gold or KIE evidence remains semantically ambiguous under the "
        "frozen deterministic rules"
    ),
    "ANNOTATION_ISSUE": (
        "Human QA confirms that the gold annotation is inconsistent or "
        "invalid; this category is never inferred from model disagreement"
    ),
}


AMBIGUITY_REASONS = {
    "AMBIGUOUS_FORMAT",
    "MISSING_DATE_COMPONENT",
    "MULTIPLE_CANDIDATES",
    "NEGATIVE_AMOUNT",
    "SOURCE_ROLE_UNCLEAR",
    "UNREADABLE_SOURCE",
    "UNSUPPORTED_CURRENCY",
    "UNSUPPORTED_TWO_DIGIT_YEAR",
}


def _is_exact(
    gold: dict[str, Any],
    prediction: dict[str, Any],
) -> bool:
    return (
        gold["annotation_status"] == prediction["value_status"]
        and gold["normalized_value"]
        == prediction["normalized_value"]
    )


def classify_root_cause(
    gold: dict[str, Any],
    real_prediction: dict[str, Any],
    oracle_prediction: dict[str, Any],
) -> str | None:
    """
    Classify one incorrect Real-OCR field using its Oracle-OCR control.

    The function is deliberately conservative. It never labels an
    annotation issue from prediction disagreement; such a label requires
    separate human QA and the affected gold must not silently remain in an
    official metric run.
    """

    if _is_exact(gold, real_prediction):
        return None

    if _is_exact(gold, oracle_prediction):
        if (
            real_prediction["predicted_value"] is None
            and oracle_prediction["predicted_value"] is not None
        ):
            return "OCR_OMISSION"

        return "OCR_SUBSTITUTION"

    oracle_reasons = set(
        oracle_prediction.get("review_reasons", [])
    )

    if (
        gold["annotation_status"] == "PRESENT"
        and oracle_prediction["predicted_value"] is None
    ):
        return "CANDIDATE_GENERATION_FAILURE"

    if (
        gold["annotation_status"] == "AMBIGUOUS"
        or oracle_reasons & AMBIGUITY_REASONS
    ):
        return "AMBIGUITY"

    if "NORMALIZATION_FAILED" in oracle_reasons:
        return "NORMALIZATION_FAILURE"

    if (
        gold.get("transcribed_value")
        == oracle_prediction["predicted_value"]
        and gold["normalized_value"]
        != oracle_prediction["normalized_value"]
    ):
        return "NORMALIZATION_FAILURE"

    return "CANDIDATE_RANKING_FAILURE"


def analyze_root_causes(
    real_pairs: Sequence[EvaluationPair],
    oracle_pairs: Sequence[EvaluationPair],
) -> dict[str, Any]:
    """Build W2 root-cause error analysis from paired OCR settings."""

    real_by_id = {
        test_id: (annotation, result)
        for test_id, annotation, result in real_pairs
    }
    oracle_by_id = {
        test_id: (annotation, result)
        for test_id, annotation, result in oracle_pairs
    }

    if set(real_by_id) != set(oracle_by_id):
        raise ValueError(
            "Real and Oracle error analysis require identical test IDs"
        )

    category_counts: Counter[str] = Counter(
        {
            category: 0
            for category in ERROR_TAXONOMY_DEFINITIONS
        }
    )
    field_counts = {
        field_name: Counter(
            {
                category: 0
                for category in ERROR_TAXONOMY_DEFINITIONS
            }
        )
        for field_name in FIELD_NAMES
    }
    errors: list[dict[str, Any]] = []

    for test_id in sorted(real_by_id):
        real_annotation, real_result = real_by_id[test_id]
        oracle_annotation, oracle_result = oracle_by_id[test_id]

        if real_annotation != oracle_annotation:
            raise ValueError(
                f"{test_id}: Real and Oracle modes must use one gold record"
            )

        for field_name in FIELD_NAMES:
            gold = real_annotation["fields"][field_name]
            real_prediction = real_result["fields"][field_name]
            oracle_prediction = oracle_result["fields"][field_name]
            category = classify_root_cause(
                gold,
                real_prediction,
                oracle_prediction,
            )

            if category is None:
                continue

            category_counts[category] += 1
            field_counts[field_name][category] += 1
            errors.append(
                {
                    "test_id": test_id,
                    "field_name": field_name,
                    "category": category,
                    "gold_status": gold["annotation_status"],
                    "gold_normalized_value": gold[
                        "normalized_value"
                    ],
                    "real_status": real_prediction["value_status"],
                    "real_predicted_value": real_prediction[
                        "predicted_value"
                    ],
                    "real_normalized_value": real_prediction[
                        "normalized_value"
                    ],
                    "oracle_status": oracle_prediction[
                        "value_status"
                    ],
                    "oracle_predicted_value": oracle_prediction[
                        "predicted_value"
                    ],
                    "oracle_normalized_value": oracle_prediction[
                        "normalized_value"
                    ],
                }
            )

    return {
        "sample_count": len(real_by_id),
        "counts": dict(category_counts),
        "counts_by_field": {
            field_name: dict(counts)
            for field_name, counts in field_counts.items()
        },
        "errors": errors,
    }
