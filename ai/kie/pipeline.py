from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable
from uuid import UUID

from ai.kie.candidates.invoice_id import (
    generate_invoice_id_candidates,
)
from ai.kie.candidates.merchant_address import (
    generate_merchant_address_candidates,
)
from ai.kie.candidates.merchant_name import (
    generate_merchant_name_candidates,
)
from ai.kie.candidates.receipt_date import (
    generate_receipt_date_candidates,
)
from ai.kie.candidates.total_amount import (
    generate_total_amount_candidates,
)
from ai.kie.confidence import field_confidence
from ai.kie.config import load_baseline_config
from ai.kie.contract import (
    validate_kie_result,
    validate_ocr_result,
)
from ai.kie.models import Candidate, NormalizationResult
from ai.kie.normalization.invoice_id import (
    normalize_invoice_id,
)
from ai.kie.normalization.merchant_address import (
    normalize_merchant_address,
)
from ai.kie.normalization.merchant_name import (
    normalize_merchant_name,
)
from ai.kie.normalization.receipt_date import (
    normalize_receipt_date,
)
from ai.kie.normalization.total_amount import (
    normalize_total_amount,
)
from ai.kie.ranking.scorer import rank_candidates
from ai.kie.review import ReviewDecision, decide_review


EXTRACTOR_NAME = "deterministic-kie-baseline"
EXTRACTOR_VERSION = "0.2.0"


FIELD_NAMES = (
    "merchant_name",
    "receipt_date",
    "total_amount",
    "invoice_id",
    "merchant_address",
)


CandidateGenerator = Callable[
    [dict[str, Any]],
    list[Candidate],
]

Normalizer = Callable[
    [Candidate],
    NormalizationResult,
]


GENERATORS: dict[str, CandidateGenerator] = {
    "merchant_name": generate_merchant_name_candidates,
    "receipt_date": generate_receipt_date_candidates,
    "total_amount": generate_total_amount_candidates,
    "invoice_id": generate_invoice_id_candidates,
    "merchant_address": generate_merchant_address_candidates,
}


NORMALIZERS: dict[str, Normalizer] = {
    "merchant_name": normalize_merchant_name,
    "receipt_date": normalize_receipt_date,
    "total_amount": normalize_total_amount,
    "invoice_id": normalize_invoice_id,
    "merchant_address": normalize_merchant_address,
}


def _utc_now_iso() -> str:
    """
    Return an RFC 3339 / JSON-Schema date-time value in UTC.
    """

    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _source_block_ids_for_field(
    ranked_candidates: list[Candidate],
    decision: ReviewDecision,
) -> tuple[str, ...]:
    """
    Determine OCR evidence attached to the machine field output.

    Normal case:
        use the best candidate's source blocks.

    MULTIPLE_CANDIDATES:
        preserve evidence from the top two competing candidates.

    The returned order is resolved later against OCR reading_order.
    """

    if not ranked_candidates:
        return ()

    candidates_to_include = [
        ranked_candidates[0],
    ]

    if (
        "MULTIPLE_CANDIDATES"
        in decision.review_reasons
        and len(ranked_candidates) >= 2
    ):
        candidates_to_include.append(
            ranked_candidates[1]
        )

    seen: set[str] = set()
    result: list[str] = []

    for candidate in candidates_to_include:
        for block_id in candidate.source_block_ids:
            if block_id not in seen:
                seen.add(block_id)
                result.append(block_id)

    return tuple(result)


def _ordered_source_evidence(
    ocr_result: dict[str, Any],
    source_block_ids: tuple[str, ...],
) -> tuple[list[str], str | None]:
    """
    Resolve source IDs against the exact OCR run and construct raw_text.

    raw_text is always built from unmodified OCR block text joined with
    newline in OCR reading_order.
    """

    if not source_block_ids:
        return [], None

    requested = set(
        source_block_ids
    )

    ordered_blocks = [
        block
        for block in sorted(
            ocr_result["blocks"],
            key=lambda item: item["reading_order"],
        )
        if block["block_id"] in requested
    ]

    resolved_ids = [
        block["block_id"]
        for block in ordered_blocks
    ]

    if set(resolved_ids) != requested:
        missing = sorted(
            requested - set(resolved_ids)
        )

        raise ValueError(
            "KIE candidate references OCR block IDs "
            "outside the source OCR run: "
            + ", ".join(missing)
        )

    raw_text = "\n".join(
        block["text"]
        for block in ordered_blocks
    )

    return resolved_ids, raw_text


def _status_from_decision(
    decision: ReviewDecision,
    normalization_result: NormalizationResult,
) -> str:
    """
    Map machine evidence/review semantics to the canonical value_status.

    LOW_CONFIDENCE alone does not make the field ambiguous. A safely
    normalized value may remain PRESENT while still requiring review.
    """

    reasons = set(
        decision.review_reasons
    )

    if "UNREADABLE_SOURCE" in reasons:
        return "UNREADABLE"

    ambiguous_reasons = {
        "MULTIPLE_CANDIDATES",
        "AMBIGUOUS_FORMAT",
        "UNSUPPORTED_CURRENCY",
        "NEGATIVE_AMOUNT",
        "MISSING_DATE_COMPONENT",
        "UNSUPPORTED_TWO_DIGIT_YEAR",
        "SOURCE_ROLE_UNCLEAR",
        "NORMALIZATION_FAILED",
    }

    if reasons & ambiguous_reasons:
        return "AMBIGUOUS"

    if normalization_result.succeeded:
        return "PRESENT"

    # Defensive fallback. In the current policy, failed normalization
    # must already produce one of the reasons above.
    return "AMBIGUOUS"


def _empty_unknown_field(
    field_name: str,
    decision: ReviewDecision,
) -> dict[str, Any]:
    """
    Build the canonical machine output when no candidate was found.

    Absence of a candidate is UNKNOWN, never automatically NOT_PRESENT.
    """

    field: dict[str, Any] = {
        "raw_text": None,
        "predicted_value": None,
        "normalized_value": None,
        "normalization": None,
        "value_status": "UNKNOWN",
        "confidence": 0.0,
        "machine_needs_review": True,
        "review_reasons": list(
            decision.review_reasons
        ),
        "review_policy_version": (
            decision.review_policy_version
        ),
        "source_block_ids": [],
    }

    if field_name == "total_amount":
        field["currency"] = "VND"

    return field


def _build_candidate_field(
    field_name: str,
    ocr_result: dict[str, Any],
    ranked_candidates: list[Candidate],
    normalization_result: NormalizationResult,
    decision: ReviewDecision,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Assemble one canonical KIE field from ranked machine evidence.
    """

    best = ranked_candidates[0]

    value_status = _status_from_decision(
        decision,
        normalization_result,
    )

    source_block_ids = _source_block_ids_for_field(
        ranked_candidates,
        decision,
    )

    (
        ordered_source_block_ids,
        raw_text,
    ) = _ordered_source_evidence(
        ocr_result,
        source_block_ids,
    )

    if value_status == "PRESENT":
        normalized_value = (
            normalization_result.normalized_value
        )

        normalization = (
            normalization_result.provenance()
        )

    else:
        # Canonical contract:
        # all non-PRESENT machine statuses expose no normalized value.
        normalized_value = None
        normalization = None

    field: dict[str, Any] = {
        "raw_text": raw_text,
        "predicted_value": best.predicted_value,
        "normalized_value": normalized_value,
        "normalization": normalization,
        "value_status": value_status,
        "confidence": field_confidence(
            ranked_candidates,
            normalization_result,
            config,
        ),
        "machine_needs_review": (
            decision.machine_needs_review
        ),
        "review_reasons": list(
            decision.review_reasons
        ),
        "source_block_ids": (
            ordered_source_block_ids
        ),
    }

    if decision.machine_needs_review:
        field["review_policy_version"] = (
            decision.review_policy_version
        )

    if field_name == "total_amount":
        field["currency"] = "VND"

    return field


def _process_field(
    field_name: str,
    ocr_result: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Run candidate generation -> ranking -> normalization -> review
    for exactly one canonical field.
    """

    generator = GENERATORS[
        field_name
    ]

    normalizer = NORMALIZERS[
        field_name
    ]

    candidates = generator(
        ocr_result,
        config=config,
    )

    ranked_candidates = rank_candidates(
        candidates
    )

    # ---------------------------------------------------------------
    # No candidate
    # ---------------------------------------------------------------

    if not ranked_candidates:
        decision = decide_review(
            field_name,
            [],
            None,
            config=config,
        )

        return _empty_unknown_field(
            field_name,
            decision,
        )

    # ---------------------------------------------------------------
    # Best candidate normalization
    # ---------------------------------------------------------------

    best = ranked_candidates[0]

    normalization_result = normalizer(
        best
    )

    decision = decide_review(
        field_name,
        ranked_candidates,
        normalization_result,
        config=config,
    )

    return _build_candidate_field(
        field_name,
        ocr_result,
        ranked_candidates,
        normalization_result,
        decision,
        config,
    )


def run_kie(
    ocr_result: dict[str, Any],
    *,
    kie_run_id: UUID,
) -> dict[str, Any]:
    """
    Run deterministic VietReceipt KIE baseline v0.1.

    Pipeline:
        validate OCRResult
        -> candidate generation
        -> deterministic ranking
        -> normalization
        -> heuristic confidence
        -> review policy
        -> canonical KIEResult
        -> validate KIEResult

    The caller creates kie_run_id. KIE consumes it and never creates
    or overwrites Backend lifecycle state.
    """

    started_at = perf_counter()

    validate_ocr_result(
        ocr_result
    )

    if not isinstance(
        kie_run_id,
        UUID,
    ):
        raise TypeError(
            "kie_run_id must be a uuid.UUID"
        )

    config = load_baseline_config()

    fields = {
        field_name: _process_field(
            field_name,
            ocr_result,
            config,
        )
        for field_name in FIELD_NAMES
    }

    duration_ms = int(
        (
            perf_counter()
            - started_at
        )
        * 1000
    )

    result: dict[str, Any] = {
        "schema_version": "1.3",
        "receipt_id": ocr_result[
            "receipt_id"
        ],
        "kie_run_id": str(
            kie_run_id
        ),
        "source_ocr_run_id": ocr_result[
            "ocr_run_id"
        ],
        "extractor": {
            "name": EXTRACTOR_NAME,
            "version": EXTRACTOR_VERSION,
        },
        "fields": fields,
        "duration_ms": duration_ms,
        "created_at": _utc_now_iso(),
    }

    validate_kie_result(
        result
    )

    return result
