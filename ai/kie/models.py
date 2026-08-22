from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    field_name: str
    predicted_value: str
    source_block_ids: tuple[str, ...]
    raw_text: str
    matched_positive_keywords: tuple[str, ...]
    matched_negative_keywords: tuple[str, ...]
    pattern_score: float
    context_score: float
    layout_score: float
    ocr_score: float
    final_score: float
    candidate_role: str = "primary"
    matched_patterns: tuple[str, ...] = ()
    ambiguity_indicators: tuple[str, ...] = ()
    normalization_indicators: tuple[str, ...] = ()


@dataclass(frozen=True)
class NormalizationResult:
    """
    Internal deterministic normalization result.

    A successful normalization has:
        normalized_value != None
        rule != None
        version != None

    A failed/unsupported normalization has:
        normalized_value == None
        rule == None
        version == None

    Review/status decisions are intentionally NOT stored here.
    Those belong to the review-policy stage.
    """

    normalized_value: str | int | None
    rule: str | None
    version: str | None

    @property
    def succeeded(self) -> bool:
        return self.normalized_value is not None

    def provenance(self) -> dict[str, str] | None:
        if not self.succeeded:
            return None

        if self.rule is None or self.version is None:
            raise ValueError(
                "successful normalization requires rule and version"
            )

        return {
            "rule": self.rule,
            "version": self.version,
        }