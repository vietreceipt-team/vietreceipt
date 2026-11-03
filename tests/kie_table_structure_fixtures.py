"""Independent synthetic source expectations; no QA or final-test designation."""

import copy

from ai.kie.v2.config import HEADER_FIELDS, LINE_FIELDS
from tests.kie_v2_fixtures import document, evidence

HEADERS = [
    ("Description", 0.05, 0.20, 0.28),
    ("Unit", 0.40, 0.20, 0.08),
    ("Quantity", 0.53, 0.20, 0.12),
    ("Unit price", 0.67, 0.20, 0.12),
    ("Amount", 0.84, 0.20, 0.12),
]
FIRST = [
    ("Service A", 0.05, 0.26, 0.20),
    ("box", 0.40, 0.26, 0.06),
    ("2", 0.62, 0.26, 0.025),
    ("50000", 0.73, 0.26, 0.05),
    ("100000", 0.90, 0.26, 0.06),
]
SECOND = [
    ("Service B", 0.05, 0.36, 0.20),
    ("pack", 0.40, 0.36, 0.06),
    ("3", 0.62, 0.36, 0.025),
    ("20000", 0.73, 0.36, 0.05),
    ("60000", 0.91, 0.36, 0.05),
]


def _cell(value, ids, status="PRESENT"):
    return {
        "annotation_status": status,
        "normalized_value": value,
        "raw_value": str(value) if value is not None else None,
        "source_block_ids": ids,
    }


def _gold(rows):
    return {
        "fields": {f: _cell(None, [], "UNKNOWN") for f in HEADER_FIELDS},
        "line_items": [
            {
                "line_id": f"source-row-{i}",
                **{
                    f: _cell(value, ids, status)
                    for f, (value, ids, status) in zip(LINE_FIELDS, row)
                },
            }
            for i, row in enumerate(rows)
        ],
    }


def _expected(values, indexes, prefix="p0"):
    return [(v, [f"{prefix}_b{i}"], "PRESENT") for v, i in zip(values, indexes)]


def cases():
    first = _expected(["Service A", "box", 2, 50000, 100000], range(5, 10))
    second = _expected(["Service B", "pack", 3, 20000, 60000], range(10, 15))
    result = {}

    def add(name, entries, rows, *, source=None, base=None):
        source = source if source is not None else evidence(entries)
        page = source["pages"][0]["evidence"] if "pages" in source else source
        currency = evidence([("Currency: VND", 0.05, 0.10, 0.30)])["blocks"][0]
        currency["block_id"] = "p0_currency"
        currency["reading_order"] = len(page["blocks"])
        page["blocks"].append(currency)
        result[name] = {
            "evidence": source,
            "gold": _gold(rows),
            "split": "development",
            "base_document_id": base or f"synthetic-{name}",
            "template_id": "synthetic-five-column-1",
            "qa_status": "SYNTHETIC_SOFTWARE_EXPECTATION_NOT_INDEPENDENT_QA",
        }

    for ruling in ("bordered", "borderless", "horizontal", "vertical"):
        add(ruling, HEADERS + FIRST + SECOND, [first, second], base="ruling-base-1")

    wrapped = copy.deepcopy(first)
    wrapped[0] = ("Service A continued", ["p0_b5", "p0_b15"], "PRESENT")
    add(
        "wrapped-description",
        HEADERS
        + FIRST
        + SECOND
        + [
            ("continued", 0.05, 0.282, 0.15),
        ],
        [wrapped, second],
    )

    staggered = list(FIRST)
    staggered[2] = ("2", 0.62, 0.278, 0.025)
    add("staggered-quantity", HEADERS + staggered + SECOND, [first, second])

    split = list(FIRST)
    split[0] = ("Service", 0.05, 0.26, 0.10)
    split_gold = copy.deepcopy(first)
    split_gold[0] = ("Service A", ["p0_b5", "p0_b15"], "PRESENT")
    add(
        "split-description",
        HEADERS
        + split
        + SECOND
        + [
            ("A", 0.17, 0.26, 0.03),
        ],
        [split_gold, second],
    )

    split_number = list(FIRST)
    split_number[3] = ("50", 0.71, 0.26, 0.025)
    split_gold = copy.deepcopy(first)
    split_gold[3] = (50000, ["p0_b8", "p0_b15"], "PRESENT")
    add(
        "split-number",
        HEADERS
        + split_number
        + SECOND
        + [
            ("000", 0.75, 0.26, 0.035),
        ],
        [split_gold, second],
    )

    merged = HEADERS + FIRST[:3] + [("50000 100000", 0.70, 0.26, 0.26)] + SECOND
    merged_first = copy.deepcopy(first)
    merged_first[3] = (50000, ["p0_b8"], "PRESENT")
    merged_first[4] = (100000, ["p0_b8"], "PRESENT")
    merged_second = _expected(["Service B", "pack", 3, 20000, 60000], range(9, 14))
    add("merged-numbers", merged, [merged_first, merged_second])

    no_unit = [entry for i, entry in enumerate(HEADERS + FIRST) if i not in {1, 6}]
    missing = _expected(["Service A", 2, 50000, 100000], range(4, 8))
    missing.insert(1, (None, [], "NOT_PRESENT"))
    add("missing-unit-column", no_unit, [missing])
    no_cell = HEADERS + FIRST[:1] + FIRST[2:]
    missing = _expected(["Service A", 2, 50000, 100000], range(5, 9))
    missing.insert(1, (None, [], "UNKNOWN"))
    add("missing-unit-cell", no_cell, [missing])

    partial = [("Product B", 0.05, 0.282, 0.20)]
    partial_gold = [("Product B", ["p0_b10"], "PRESENT")] + [
        (None, [], "UNKNOWN") for _ in range(4)
    ]
    add("ambiguous-partial-next-item", HEADERS + FIRST + partial, [first, partial_gold])

    repeat = [(v, x, 0.32, w) for v, x, _, w in HEADERS]
    repeated_second = _expected(["Service B", "pack", 3, 20000, 60000], range(15, 20))
    add("repeated-header", HEADERS + FIRST + repeat + SECOND, [first, repeated_second])

    page2 = evidence(HEADERS + FIRST, prefix="p1")
    page2_expected = _expected(
        ["Service A", "box", 2, 50000, 100000], range(5, 10), "p1"
    )
    add(
        "multiple-pages",
        [],
        [first, page2_expected],
        source=document(
            evidence(HEADERS + FIRST),
            page2,
        ),
    )
    add(
        "unheaded", FIRST, [_expected(["Service A", "box", 2, 50000, 100000], range(5))]
    )
    add("empty", [], [])
    return result
