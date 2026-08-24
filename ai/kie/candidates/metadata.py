from __future__ import annotations

import re


UNREADABLE_SOURCE_PATTERN = re.compile(
    r"(?:\N{REPLACEMENT CHARACTER}|\[(?:UNREADABLE|ILLEGIBLE)\])",
    flags=re.IGNORECASE | re.UNICODE,
)


def merge_indicators(
    *indicator_groups: tuple[str, ...],
) -> tuple[str, ...]:
    """Merge deterministic candidate indicators without duplicates."""

    return tuple(
        dict.fromkeys(
            indicator
            for group in indicator_groups
            for indicator in group
        )
    )


def unreadable_source_indicators(
    text: str,
) -> tuple[str, ...]:
    """Flag explicit OCR unreadability markers without guessing text."""

    if UNREADABLE_SOURCE_PATTERN.search(text):
        return ("unreadable_source",)

    return ()
