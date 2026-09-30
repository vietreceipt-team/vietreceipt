"""Candidate ranking, conservative selection and machine-only review cells."""

from dataclasses import dataclass

from .config import LOW_SCORE, REVIEW_VERSION, SCORE_VERSION, TIE_MARGIN
from .evidence import Block
from .normalization import folded, normalize


@dataclass(frozen=True)
class Candidate:
    value: str
    blocks: tuple[Block, ...]
    explicit_role: bool = True
    aligned: bool = True


def score(candidate: Candidate, normalizable: bool) -> float:
    # Four documented signals; evidence confidence is only a low-quality penalty.
    quality_penalty = any(
        b.evidence_confidence is not None and b.evidence_confidence < 0.5
        for b in candidate.blocks
    )
    return round(
        max(
            0,
            0.35
            + 0.25 * candidate.explicit_role
            + 0.2 * candidate.aligned
            + 0.15 * normalizable
            - 0.2 * quality_penalty,
        ),
        4,
    )


def add_reason(cell, reason):
    if reason not in cell["review_reasons"]:
        cell["review_reasons"].append(reason)
    cell["machine_needs_review"] = True


def select(field: str, candidates: list[Candidate], *, currency=None, absent=False):
    cell = {
        "raw_text": None,
        "predicted_value": None,
        "normalized_value": None,
        "normalization": None,
        "value_status": "NOT_PRESENT" if absent else "UNKNOWN",
        "confidence": None,
        "heuristic_score": 0.0,
        "score_version": SCORE_VERSION,
        "machine_needs_review": not absent,
        "review_reasons": [] if absent else ["NO_CANDIDATE"],
        "review_policy_version": REVIEW_VERSION,
        "source_block_ids": [],
    }
    if not candidates:
        return cell
    ranked = []
    for candidate in candidates:
        raw = "\n".join(b.text for b in candidate.blocks)
        result = normalize(field, candidate.value, raw, currency)
        ranked.append((score(candidate, result[0] is not None), candidate, result))
    ranked.sort(
        key=lambda r: (
            -r[0],
            tuple((b.page, b.reading_order, b.block_id) for b in r[1].blocks),
        )
    )
    best_score, best, (value, provenance, failure) = ranked[0]
    selected = [best]
    reasons = []
    status = "PRESENT"
    if folded(best.value) in {"khong co", "khong ap dung", "n/a", "none"}:
        status, value, provenance = "NOT_PRESENT", None, None
    elif not best.value.strip() or any(c in best.value for c in "?\ufffd"):
        status = "UNREADABLE"
        reasons.append("UNREADABLE_SOURCE")
    elif failure:
        status = "AMBIGUOUS"
        reasons.extend(
            [failure, "NORMALIZATION_FAILED"]
            if failure != "NORMALIZATION_FAILED"
            else [failure]
        )
    for other_score, other, result in ranked[1:]:
        equivalent = (
            result[0] == value if value is not None else other.value == best.value
        )
        if (
            field == "currency" or best_score - other_score <= TIE_MARGIN
        ) and not equivalent:
            status = "AMBIGUOUS"
            reasons.append("MULTIPLE_CANDIDATES")
            if field == "currency" and result[2] == "UNSUPPORTED_CURRENCY":
                reasons.append("UNSUPPORTED_CURRENCY")
            selected.append(other)
    if not best.explicit_role:
        status = "AMBIGUOUS"
        reasons.append("SOURCE_ROLE_UNCLEAR")
    if best_score < LOW_SCORE:
        reasons.append("LOW_CONFIDENCE")
    blocks = {b.block_id: b for c in selected for b in c.blocks}
    ordered = sorted(blocks.values(), key=lambda b: (b.page, b.reading_order))
    cell.update(
        raw_text="\n".join(b.text for b in ordered),
        predicted_value=best.value,
        normalized_value=value if status == "PRESENT" else None,
        normalization=provenance if status == "PRESENT" else None,
        value_status=status,
        heuristic_score=best_score,
        machine_needs_review=bool(reasons),
        review_reasons=list(dict.fromkeys(reasons)),
        source_block_ids=[b.block_id for b in ordered],
    )
    return cell
