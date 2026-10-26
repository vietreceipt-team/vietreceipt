"""Proposed source-spatial metric kernel. Not a QA gate or final-run authorization.

TV5 must feed immutable machine outputs from original files, with source hash /
identity linkage checked and independently reviewed source regions. The pending
TV2 package may be inspected but MUST NOT be scored as a reviewed benchmark.
"""

import math
from collections import defaultdict
from uuid import UUID

from .contract import validate_result
from .evidence import flatten
from .evaluation import metrics, validate_gold

SOURCE_MATCHING_VERSION = "page-bbox-positive-iou-cardinality-1.0"


def validate_regions(regions, gold):
    expected = [r["line_id"] for r in gold["line_items"]]
    ids = [r["line_id"] for r in regions]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError("Exactly one source region per gold line is required")
    for r in regions:
        b = r["bounds"]
        if (
            type(r["page_index"]) is not int
            or r["page_index"] < 0
            or len(b) != 4
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
                for v in b
            )
            or b[0] >= b[2]
            or b[1] >= b[3]
        ):
            raise ValueError("Invalid normalized top-left source-page rectangle")


def prediction_regions(rows, evidence):
    blocks = {b.block_id: b for b in flatten(evidence)}
    result = []
    for row in rows:
        pages = defaultdict(list)
        for block_id in row["source_block_ids"]:
            if block_id not in blocks:
                raise ValueError("Unknown predicted source block")
            b = blocks[block_id]
            pages[b.page].append(b)
        result.append(
            {
                page: [
                    min(b.left for b in group),
                    min(b.top for b in group),
                    max(b.right for b in group),
                    max(b.bottom for b in group),
                ]
                for page, group in pages.items()
            }
        )
    return result


def iou(a, b):
    area = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - area
    return area / union if union else 0


def spatial_matches(rows, evidence, gold, regions):
    """Maximum cardinality for positive area overlap, page-aware, value-blind.

    Gold region identities only map source rows to gold rows; no gold block IDs
    enter this function. Gold traversal is page/top/left/index; edges prefer IoU
    then prediction index (source reading order), never normalized text or money.
    A merged box can overlap multiple gold rows but can own only one match.
    """
    validate_regions(regions, gold)
    by_id = {r["line_id"]: r for r in regions}
    target = [by_id[r["line_id"]] for r in gold["line_items"]]
    boxes = prediction_regions(rows, evidence)
    edges = []
    for r in target:
        overlaps = [
            (iou(r["bounds"], box[r["page_index"]]), j)
            for j, box in enumerate(boxes)
            if r["page_index"] in box
        ]
        edges.append(
            [
                j
                for score, j in sorted(overlaps, key=lambda x: (-x[0], x[1]))
                if score > 0
            ]
        )
    owners = {}

    def assign(i, seen):
        for j in edges[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in owners or assign(owners[j], seen):
                owners[j] = i
                return True
        return False

    for i in sorted(
        range(len(target)),
        key=lambda i: (
            target[i]["page_index"],
            target[i]["bounds"][1],
            target[i]["bounds"][0],
            i,
        ),
    ):
        assign(i, set())
    return sorted((i, j) for j, i in owners.items())


def source_metrics(cases):
    """Pure metric kernel, like evaluation.metrics; caller owns reviewed QA gate.

    Each case is (result or None, source_gold, evidence or None, source_regions).
    A None result is a failed eligible input, NOT an empty successful prediction.
    The gold must carry no OCR block links. Input association/source hashes and
    geometry transforms must be validated by the original-file runner (TV5).
    """
    matches = []
    for result, gold, evidence, regions in cases:
        validate_gold(gold, None, gold, aligned=False)
        validate_regions(regions, gold)
        if result is None:
            matches.append([])
        else:
            validate_result(result, evidence, kie_run_id=UUID(result["kie_run_id"]))
            matches.append(
                spatial_matches(result["line_items"], evidence, gold, regions)
            )
    report = metrics(
        [(result, gold) for result, gold, _, _ in cases], matches_by_document=matches
    )
    report.update(
        matching_version=SOURCE_MATCHING_VERSION,
        matching_scope="source_regions_not_gold_block_ids",
        qa_scope="metric_kernel_only; caller_must_gate_reviewed_source_gold_and_identity",
    )
    return report
