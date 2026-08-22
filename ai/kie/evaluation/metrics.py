from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from ai.kie.pipeline import FIELD_NAMES


EvaluationPair = tuple[
    str,
    dict[str, Any],
    dict[str, Any],
]


def _ratio(
    numerator: int,
    denominator: int,
) -> float:
    if denominator == 0:
        return 0.0

    return round(
        numerator / denominator,
        6,
    )


def _error_category(
    *,
    gold_status: str,
    predicted_status: str,
    gold_value: str | int | None,
    predicted_value: str | int | None,
) -> str | None:
    if gold_status != predicted_status:
        if (
            gold_status == "PRESENT"
            and predicted_status != "PRESENT"
        ):
            return "MISSED_PRESENT"

        if (
            gold_status != "PRESENT"
            and predicted_status == "PRESENT"
        ):
            return "SPURIOUS_PRESENT"

        return "STATUS_MISMATCH"

    if (
        gold_status == "PRESENT"
        and gold_value != predicted_value
    ):
        return "NORMALIZATION_MISMATCH"

    return None


def _empty_counts() -> Counter[str]:
    return Counter(
        {
            "decisions": 0,
            "exact": 0,
            "status_correct": 0,
            "gold_present": 0,
            "normalization_correct": 0,
            "predicted_present": 0,
            "reviewed": 0,
            "true_positive": 0,
            "false_positive": 0,
            "false_negative": 0,
        }
    )


def _summarize_counts(
    counts: Counter[str],
) -> dict[str, int | float]:
    precision = _ratio(
        counts["true_positive"],
        counts["true_positive"]
        + counts["false_positive"],
    )
    recall = _ratio(
        counts["true_positive"],
        counts["true_positive"]
        + counts["false_negative"],
    )

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = round(
            2 * precision * recall
            / (precision + recall),
            6,
        )

    return {
        "decision_count": counts["decisions"],
        "gold_present_count": counts["gold_present"],
        "predicted_present_count": counts[
            "predicted_present"
        ],
        "exact_match_accuracy": _ratio(
            counts["exact"],
            counts["decisions"],
        ),
        "status_accuracy": _ratio(
            counts["status_correct"],
            counts["decisions"],
        ),
        "normalization_accuracy": _ratio(
            counts["normalization_correct"],
            counts["gold_present"],
        ),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "coverage": _ratio(
            counts["predicted_present"],
            counts["decisions"],
        ),
        "review_rate": _ratio(
            counts["reviewed"],
            counts["decisions"],
        ),
    }


def compute_field_metrics(
    pairs: Sequence[EvaluationPair],
) -> dict[str, Any]:
    """
    Compute deterministic field-level KIE metrics.

    Extraction true positives require both PRESENT status and an exact
    normalized-value match. A wrong PRESENT value is counted as both a
    false positive and a false negative. Exact match requires status and
    normalized value to match, so null values cannot hide status errors.
    """

    counts_by_field = {
        field_name: _empty_counts()
        for field_name in FIELD_NAMES
    }
    overall_counts = _empty_counts()
    errors: list[dict[str, Any]] = []
    error_counts: Counter[str] = Counter()

    for test_id, annotation, kie_result in pairs:
        for field_name in FIELD_NAMES:
            gold = annotation["fields"][field_name]
            prediction = kie_result["fields"][field_name]

            gold_status = gold["annotation_status"]
            predicted_status = prediction["value_status"]
            gold_value = gold["normalized_value"]
            predicted_value = prediction[
                "normalized_value"
            ]

            exact = (
                gold_status == predicted_status
                and gold_value == predicted_value
            )
            status_correct = (
                gold_status == predicted_status
            )
            gold_present = gold_status == "PRESENT"
            predicted_present = (
                predicted_status == "PRESENT"
            )
            normalization_correct = (
                gold_present
                and predicted_present
                and gold_value == predicted_value
            )

            counters = (
                counts_by_field[field_name],
                overall_counts,
            )

            for counts in counters:
                counts["decisions"] += 1
                counts["exact"] += int(exact)
                counts["status_correct"] += int(
                    status_correct
                )
                counts["gold_present"] += int(
                    gold_present
                )
                counts["normalization_correct"] += int(
                    normalization_correct
                )
                counts["predicted_present"] += int(
                    predicted_present
                )
                counts["reviewed"] += int(
                    prediction["machine_needs_review"]
                )

                if normalization_correct:
                    counts["true_positive"] += 1
                else:
                    if predicted_present:
                        counts["false_positive"] += 1
                    if gold_present:
                        counts["false_negative"] += 1

            category = _error_category(
                gold_status=gold_status,
                predicted_status=predicted_status,
                gold_value=gold_value,
                predicted_value=predicted_value,
            )

            if category is not None:
                error_counts[category] += 1
                errors.append(
                    {
                        "test_id": test_id,
                        "field_name": field_name,
                        "category": category,
                        "gold_status": gold_status,
                        "predicted_status": predicted_status,
                        "gold_normalized_value": gold_value,
                        "predicted_normalized_value": (
                            predicted_value
                        ),
                    }
                )

    return {
        "sample_count": len(pairs),
        "overall": _summarize_counts(
            overall_counts
        ),
        "fields": {
            field_name: _summarize_counts(
                counts_by_field[field_name]
            )
            for field_name in FIELD_NAMES
        },
        "error_taxonomy": {
            "counts": dict(
                sorted(error_counts.items())
            ),
            "errors": errors,
        },
    }
