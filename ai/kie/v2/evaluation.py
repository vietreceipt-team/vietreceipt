"""Frozen-manifest evaluator. Synthetic unit diagnostics are never thesis results."""

import copy
import hashlib
import json
import math
import platform
import subprocess
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from . import extract_invoice, extract_with_grouping
from .config import (
    BASELINE_GROUPING,
    CONFIGURATION,
    GROUPING_CONFIGURATIONS,
    GROUPING_EXTRACTORS,
    HEADER_FIELDS,
    INTERVAL_GROUPING,
    LINE_FIELDS,
    MONEY_FIELDS,
)
from .evidence import flatten

ROOT = Path(__file__).resolve().parents[3]
VERSION = "invoice-evaluation-2.2.0"
MATCHING_VERSION = "source-overlap-cardinality-1.0"
TAXONOMY = (
    "NO_CANDIDATE",
    "WRONG_CANDIDATE",
    "ROLE_CONFUSION",
    "NORMALIZATION_ERROR",
    "ROW_DETECTION_ERROR",
    "COLUMN_ALIGNMENT_ERROR",
    "OCR_PROPAGATION",
    "MULTIPLE_CANDIDATES",
    "CONSISTENCY_WARNING",
)
ANNOTATION_STATUSES = (
    "PRESENT",
    "NOT_PRESENT",
    "UNKNOWN",
    "UNREADABLE",
    "AMBIGUOUS",
)


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def correct(prediction, gold):
    return (prediction["value_status"], prediction["normalized_value"]) == (
        gold["annotation_status"],
        gold["normalized_value"],
    )


def row_matches(predictions, gold):
    """One-to-one maximum cardinality matching using evidence, never cell values.

    Matching is independent of cell correctness. A deterministic augmenting-path
    matcher maximizes detected row count; overlap priority breaks ties.
    """
    edges = []
    for target in gold:
        ids = {i for f in LINE_FIELDS for i in target[f]["source_block_ids"]}
        ranked = sorted(
            (
                (len(ids & set(p["source_block_ids"])), j)
                for j, p in enumerate(predictions)
            ),
            key=lambda x: (-x[0], x[1]),
        )
        edges.append([j for overlap, j in ranked if overlap])
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

    for i in range(len(gold)):
        assign(i, set())
    return sorted((i, j) for j, i in owners.items())


def known(cell):
    return cell["annotation_status"] != "UNKNOWN"


def metrics(pairs, *, matches_by_document=None):
    # A source-level failed input remains in all eligible denominators. This
    # placeholder is internal scoring state, never an emitted machine prediction.
    failed = [result is None for result, _ in pairs]
    missing = {
        "fields": {
            f: {
                "value_status": "UNKNOWN",
                "normalized_value": None,
                "machine_needs_review": False,
                "review_reasons": ["PROCESSING_FAILED"],
            }
            for f in HEADER_FIELDS
        },
        "line_items": [],
        "consistency": {"checks": []},
    }
    pairs = [
        (result if result is not None else missing, gold) for result, gold in pairs
    ]
    fields = {}
    errors = Counter({key: 0 for key in TAXONOMY})
    for field in HEADER_FIELDS:
        count = Counter(
            {
                key: 0
                for key in (
                    "total",
                    "scored",
                    "unknown",
                    "correct",
                    "predicted_present",
                    "gold_present",
                    "true_positive",
                    "false_positive",
                    "false_negative",
                    "review",
                    "miss",
                    "wrong",
                    "false_value",
                    "unresolved",
                )
            }
        )
        gold_statuses = Counter({status: 0 for status in ANNOTATION_STATUSES})
        predicted_statuses = Counter({status: 0 for status in ANNOTATION_STATUSES})
        for result, gold in pairs:
            p, g = result["fields"][field], gold["fields"][field]
            count["total"] += 1
            gold_statuses[g["annotation_status"]] += 1
            if not known(g):
                count["unknown"] += 1
                continue
            predicted_statuses[p["value_status"]] += 1
            ok = correct(p, g)
            present, expected = (
                p["value_status"] == "PRESENT",
                g["annotation_status"] == "PRESENT",
            )
            count.update(
                scored=1,
                correct=int(ok),
                predicted_present=int(present),
                gold_present=int(expected),
                true_positive=int(ok and expected),
                false_positive=int(present and not (ok and expected)),
                false_negative=int(expected and not (ok and expected)),
                review=int(p["machine_needs_review"]),
                miss=int(expected and not present),
                wrong=int(expected and present and not ok),
                false_value=int(not expected and present),
                unresolved=int(
                    p["value_status"] in {"UNKNOWN", "UNREADABLE", "AMBIGUOUS"}
                ),
            )
            if not ok:
                reasons = p["review_reasons"]
                category = (
                    "NO_CANDIDATE"
                    if "NO_CANDIDATE" in reasons
                    else "ROLE_CONFUSION"
                    if "SOURCE_ROLE_UNCLEAR" in reasons
                    else "NORMALIZATION_ERROR"
                    if "NORMALIZATION_FAILED" in reasons
                    else "MULTIPLE_CANDIDATES"
                    if "MULTIPLE_CANDIDATES" in reasons
                    else "WRONG_CANDIDATE"
                )
                errors[category] += 1
        precision = ratio(count["true_positive"], count["predicted_present"])
        recall = ratio(count["true_positive"], count["gold_present"])
        fields[field] = {
            **count,
            "metric_definition": "exact-value-extraction-1.0",
            "gold_status_counts": dict(gold_statuses),
            "predicted_status_counts_on_known_gold": dict(predicted_statuses),
            "exact_match": ratio(count["correct"], count["scored"]),
            "coverage": ratio(count["scored"], count["total"]),
            "precision": precision,
            "recall": recall,
            "f1": ratio(
                2 * count["true_positive"],
                count["predicted_present"] + count["gold_present"],
            ),
            "review_rate": ratio(count["review"], count["scored"]),
        }
    extraction = Counter(
        {
            key: sum(field[key] for field in fields.values())
            for key in ("true_positive", "false_positive", "false_negative")
        }
    )
    totals = Counter(
        {
            key: 0
            for key in (
                "gold_rows",
                "predicted_rows",
                "matched_rows",
                "complete_rows",
                "extra_rows",
                "documents",
                "complete_header",
                "complete_table",
                "complete_invoice",
                "scoreable_gold_rows",
                "scoreable_header_documents",
                "scoreable_table_documents",
                "scoreable_invoice_documents",
                "failed_documents",
            )
        }
    )
    columns = Counter({f: 0 for f in LINE_FIELDS})
    column_scored = Counter({f: 0 for f in LINE_FIELDS})
    for index, (result, gold) in enumerate(pairs):
        predicted, expected = result["line_items"], gold["line_items"]
        matches = (
            matches_by_document[index]
            if matches_by_document is not None
            else row_matches(predicted, expected)
        )
        complete = 0
        row_known = [all(known(r[f]) for f in LINE_FIELDS) for r in expected]
        for i, j in matches:
            for f in LINE_FIELDS:
                if known(expected[i][f]):
                    ok = correct(predicted[j][f], expected[i][f])
                    columns[f] += int(ok)
                    column_scored[f] += 1
                    errors["COLUMN_ALIGNMENT_ERROR"] += int(not ok)
            complete += row_known[i] and all(
                correct(predicted[j][f], expected[i][f]) for f in LINE_FIELDS
            )
        header_known = all(known(gold["fields"][f]) for f in HEADER_FIELDS)
        table_known = all(row_known)
        full_header = (
            not failed[index]
            and header_known
            and all(
                correct(result["fields"][f], gold["fields"][f]) for f in HEADER_FIELDS
            )
        )
        full_table = (
            not failed[index]
            and table_known
            and complete == len(expected) == len(predicted)
        )
        totals.update(
            gold_rows=len(expected),
            predicted_rows=len(predicted),
            matched_rows=len(matches),
            complete_rows=complete,
            extra_rows=len(predicted) - len(matches),
            documents=1,
            complete_header=int(full_header),
            complete_table=int(full_table),
            complete_invoice=int(full_header and full_table),
            scoreable_gold_rows=sum(row_known),
            scoreable_header_documents=int(header_known),
            scoreable_table_documents=int(table_known),
            scoreable_invoice_documents=int(header_known and table_known),
            failed_documents=int(failed[index]),
        )
        errors["ROW_DETECTION_ERROR"] += (
            len(expected) + len(predicted) - 2 * len(matches)
        )
        errors["CONSISTENCY_WARNING"] += sum(
            c["status"] == "WARNING" for c in result["consistency"]["checks"]
        )
    return {
        "scope": "13_headers_and_line_items_only; tax_breakdown_not_scored",
        "status_policy": "known-gold-only-1.0; UNKNOWN excluded, other statuses scored",
        "headers": fields,
        "header_coverage": {
            "eligible": sum(c["total"] for c in fields.values()),
            "scored": sum(c["scored"] for c in fields.values()),
            "unknown": sum(c["unknown"] for c in fields.values()),
        },
        "header_status_counts": {
            "gold": {
                status: sum(
                    field["gold_status_counts"][status] for field in fields.values()
                )
                for status in ANNOTATION_STATUSES
            },
            "predicted_on_known_gold": {
                status: sum(
                    field["predicted_status_counts_on_known_gold"][status]
                    for field in fields.values()
                )
                for status in ANNOTATION_STATUSES
            },
        },
        "header_micro_accuracy": ratio(
            sum(c["correct"] for c in fields.values()),
            sum(c["scored"] for c in fields.values()),
        ),
        "header_exact_value_extraction": {
            "metric_definition": "exact-value-extraction-1.0",
            **extraction,
            "precision": ratio(
                extraction["true_positive"],
                extraction["true_positive"] + extraction["false_positive"],
            ),
            "recall": ratio(
                extraction["true_positive"],
                extraction["true_positive"] + extraction["false_negative"],
            ),
            "f1": ratio(
                2 * extraction["true_positive"],
                2 * extraction["true_positive"]
                + extraction["false_positive"]
                + extraction["false_negative"],
            ),
        },
        "lines": {
            **totals,
            "detection_true_positive": totals["matched_rows"],
            "detection_false_positive": totals["predicted_rows"]
            - totals["matched_rows"],
            "detection_false_negative": totals["gold_rows"] - totals["matched_rows"],
            "detection_precision": ratio(
                totals["matched_rows"], totals["predicted_rows"]
            ),
            "detection_recall": ratio(totals["matched_rows"], totals["gold_rows"]),
            "detection_f1": ratio(
                2 * totals["matched_rows"],
                totals["predicted_rows"] + totals["gold_rows"],
            ),
            "extra_row_rate": ratio(totals["extra_rows"], totals["predicted_rows"]),
            "matched_cells_scored": sum(column_scored.values()),
            "matched_cells_unknown": totals["matched_rows"] * len(LINE_FIELDS)
            - sum(column_scored.values()),
            "per_column_scored": dict(column_scored),
            "matched_cells_correct": sum(columns.values()),
            "per_column_correct": dict(columns),
            "matched_row_cell_correctness": ratio(
                sum(columns.values()), sum(column_scored.values())
            ),
            "per_column_correctness": {
                f: ratio(n, column_scored[f]) for f, n in columns.items()
            },
            "complete_line_accuracy": ratio(
                totals["complete_rows"], totals["scoreable_gold_rows"]
            ),
        },
        "complete_header_accuracy": ratio(
            totals["complete_header"], totals["scoreable_header_documents"]
        ),
        "complete_table_accuracy": ratio(
            totals["complete_table"], totals["scoreable_table_documents"]
        ),
        "complete_invoice_accuracy": ratio(
            totals["complete_invoice"], totals["scoreable_invoice_documents"]
        ),
        "error_taxonomy": dict(errors),
    }


def load_artifact(base, reference):
    path = (base / reference["path"]).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("Artifact path escapes manifest directory")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != reference["sha256"]:
        raise ValueError("Artifact hash mismatch")
    artifact = json.loads(data)
    json.dumps(artifact, allow_nan=False)
    return artifact


def validate_gold(gold, evidence, manifest, *, aligned=True):
    schema = json.loads(
        (ROOT / "schemas/invoice-annotation.v2.schema.json").read_text()
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(gold)
    ids = {b.block_id for b in flatten(evidence)} if aligned else set()
    if (
        (aligned and gold["receipt_id"] != evidence["receipt_id"])
        or set(gold["fields"]) != set(HEADER_FIELDS)
        or any(
            gold[k] != manifest[k]
            for k in ("dataset_family", "dataset_snapshot", "split", "synthetic")
        )
    ):
        raise ValueError("Gold identity, fields or dataset provenance mismatch")
    line_ids = [r["line_id"] for r in gold["line_items"]]
    if len(line_ids) != len(set(line_ids)):
        raise ValueError("Duplicate gold line ID")
    all_cells = list(gold["fields"].values()) + [
        r[f] for r in gold["line_items"] for f in LINE_FIELDS
    ]
    for cell in all_cells:
        if (
            not set(cell["source_block_ids"]) <= ids
            or (
                cell["annotation_status"] == "PRESENT"
                and (
                    cell["normalized_value"] is None
                    or (aligned and not cell["source_block_ids"])
                )
            )
            or (
                cell["annotation_status"] != "PRESENT"
                and cell["normalized_value"] is not None
            )
        ):
            raise ValueError("Gold value/evidence invariant failed")
    for row in gold["line_items"]:
        if aligned and not any(row[f]["source_block_ids"] for f in LINE_FIELDS):
            raise ValueError("Gold row needs evidence for detection matching")
    currency = gold["fields"]["currency"]["normalized_value"]
    named_cells = list(gold["fields"].items()) + [
        (f, r[f]) for r in gold["line_items"] for f in LINE_FIELDS
    ]
    for field, cell in named_cells:
        if cell["annotation_status"] != "PRESENT":
            continue
        value = cell["normalized_value"]
        if field in MONEY_FIELDS:
            # Match the machine contract: VND is integer-only, while an
            # explicitly printed USD currency supports up to two decimals.
            valid = type(value) is int and value >= 0
            if currency == "USD" and type(value) in (int, float):
                scaled_value = Decimal(str(value)) * 100
                valid = (
                    math.isfinite(value)
                    and value >= 0
                    and scaled_value == scaled_value.to_integral_value()
                )
        elif field == "quantity":
            valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
        else:
            valid = isinstance(value, str) and bool(value.strip())
        if field == "invoice_date" and valid:
            valid = date.fromisoformat(value).isoformat() == value
        if not valid:
            raise ValueError("Gold normalized value has wrong canonical type")


def implementation_digest():
    """Content-address the implementation, including uncommitted implementation files."""
    paths = sorted((ROOT / "ai/kie/v2").glob("*.py"))
    paths += sorted((ROOT / "ai/kie/normalization").glob("*.py"))
    paths += [
        ROOT / "ai/kie/models.py",
        ROOT / "ai/kie/contract.py",
        ROOT / "schemas/invoice-kie-result.v2.schema.json",
        ROOT / "schemas/ocr-result.schema.json",
        ROOT / "schemas/invoice-annotation.v2.schema.json",
        ROOT / "scripts/evaluate_invoice_kie.py",
        ROOT / "scripts/inspect_invoice_handoff.py",
        ROOT / "schemas/invoice-kie-experiment.v1.schema.json",
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(
            str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0"
        )
    return digest.hexdigest()


def _experiment(manifest, comparison, grouping):
    """A new opt-in manifest contract; legacy single-config gate stays strict."""
    if comparison:
        if manifest["split"] not in {"train", "validation"}:
            raise ValueError(
                "A/B tuning is restricted to train/validation; final test stays locked"
            )
        expected = {
            "protocol": "grouping-ab-1.0",
            "evaluator_version": VERSION,
            "configurations": GROUPING_CONFIGURATIONS,
        }
        schema = json.loads(
            (ROOT / "schemas/invoice-kie-experiment.v1.schema.json").read_text()
        )
        Draft202012Validator(schema).validate(manifest.get("experiment"))
        if manifest.get("experiment") != expected:
            raise ValueError(
                "A/B requires the exact reviewed experiment/configurations declaration"
            )
        if manifest["configuration"] != CONFIGURATION:
            raise ValueError(
                "A/B manifest configuration must retain the baseline anchor"
            )
        return [BASELINE_GROUPING, INTERVAL_GROUPING]
    if manifest["configuration"] != GROUPING_CONFIGURATIONS[grouping]:
        raise ValueError("Manifest configuration does not authorize requested grouping")
    return [grouping]


def _sample_result(result, gold, raw_protocol):
    matches = row_matches(result["line_items"], gold["line_items"])
    ablation = {"status": "NOT_RUN_QA_RAW_GOLD_REQUIRED", "metrics": None}
    if raw_protocol == "selected-value-text-v1":
        cells = [(result["fields"][f], gold["fields"][f]) for f in HEADER_FIELDS]
        cells += [
            (result["line_items"][j][f], gold["line_items"][i][f])
            for i, j in matches
            for f in LINE_FIELDS
        ]
        cells = [(p, g) for p, g in cells if g["annotation_status"] == "PRESENT"]
        # Raw gold is explicitly QA-approved selected-value text, never canonical
        # money coerced to a printed string. Missing predictions count as wrong.
        before = sum(p["predicted_value"] == g["raw_value"] for p, g in cells)
        after = sum(correct(p, g) for p, g in cells)
        ablation = {
            "status": "COMPLETED",
            "protocol": raw_protocol,
            "scope": "present_headers_and_present_cells_in_matched_rows",
            "metrics": {
                "scored": len(cells),
                "predicted_correct": before,
                "normalized_correct": after,
                "predicted_exact_match": ratio(before, len(cells)),
                "normalized_exact_match": ratio(after, len(cells)),
            },
        }
    gold_ids = [
        set(i for f in LINE_FIELDS for i in row[f]["source_block_ids"])
        for row in gold["line_items"]
    ]
    return {
        "metrics": metrics([(result, gold)]),
        "row_matches": [
            {
                "gold_index": i,
                "prediction_index": j,
                "gold_line_id": gold["line_items"][i]["line_id"],
                "prediction_line_id": result["line_items"][j]["line_id"],
                "cells_correct": {
                    f: (
                        correct(result["line_items"][j][f], gold["line_items"][i][f])
                        if known(gold["line_items"][i][f])
                        else None
                    )
                    for f in LINE_FIELDS
                },
                "complete": all(known(gold["line_items"][i][f]) for f in LINE_FIELDS)
                and all(
                    correct(result["line_items"][j][f], gold["line_items"][i][f])
                    for f in LINE_FIELDS
                ),
            }
            for i, j in matches
        ],
        "unmatched_gold_indices": sorted(
            set(range(len(gold["line_items"]))) - {i for i, _ in matches}
        ),
        "unmatched_prediction_indices": sorted(
            set(range(len(result["line_items"]))) - {j for _, j in matches}
        ),
        "shared_gold_evidence_pairs": sum(
            bool(a & b) for i, a in enumerate(gold_ids) for b in gold_ids[i + 1 :]
        ),
        "normalization_ablation": ablation,
        "prediction": result,
    }


def _delta(baseline, variant):
    if isinstance(baseline, dict):
        return {key: _delta(value, variant[key]) for key, value in baseline.items()}
    if type(baseline) in (int, float) and type(variant) in (int, float):
        return variant - baseline
    return None


def evaluate(manifest_path: Path, *, comparison=False, grouping=BASELINE_GROUPING):
    report = {
        "status": "WAITING_FOR_VERIFIED_V2_GOLD",
        "metrics": None,
        "modes": None,
        "propagation_gap": None,
        "variants": None,
        "delta": None,
        "evaluated": 0,
        "reasons": [],
        "failures": [],
        "samples": [],
        "coverage": {
            "required": None,
            "manifest_records": 0,
            "eligible": 0,
            "processed": 0,
            "evaluated": 0,
            "fraction": None,
        },
        "evaluator_version": VERSION,
        "matching_version": MATCHING_VERSION,
        "protocol_status": "PROPOSED_PENDING_TV1_TV2_CONFIRMATION",
        "extractor": dict(GROUPING_EXTRACTORS.get(grouping, {})),
        "configuration": dict(GROUPING_CONFIGURATIONS.get(grouping, {})),
        "comparison": comparison,
        "grouping": grouping,
        "manifest": str(manifest_path),
        "git_commit": None,
        "git_dirty": None,
        "implementation_sha256": implementation_digest(),
        "environment": {
            "python": platform.python_version(),
            "jsonschema": version("jsonschema"),
        },
    }
    try:
        if grouping not in GROUPING_CONFIGURATIONS:
            raise ValueError("Unknown grouping")
        if comparison and grouping != BASELINE_GROUPING:
            raise ValueError("A/B always uses the baseline anchor; omit grouping")
        report["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        report["git_dirty"] = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        )
        data = manifest_path.read_bytes()
        manifest = json.loads(data)
        json.dumps(manifest, allow_nan=False)
        report["manifest_sha256"] = hashlib.sha256(data).hexdigest()
        report["coverage"].update(
            required=manifest.get("sample_count"),
            manifest_records=len(manifest.get("records", [])),
        )
        if manifest.get("schema_version") == "tv2-tv4-handoff-candidate-0.1":
            raise ValueError(
                "TV2 candidate package is not reviewed gold: source/alignment QA and the exact experiment declaration are required; use inspect_invoice_handoff.py for unscored diagnostics"
            )
        for key in (
            "dataset_family",
            "dataset_snapshot",
            "split",
            "synthetic",
            "template_regime",
        ):
            report[key] = manifest[key]
        report["coverage"].update(
            required=manifest["sample_count"], manifest_records=len(manifest["records"])
        )
        if type(manifest["synthetic"]) is not bool or any(
            not isinstance(manifest[k], str) or not manifest[k].strip()
            for k in (
                "dataset_family",
                "dataset_snapshot",
                "template_regime",
                "verified_by",
            )
        ):
            raise ValueError("Missing typed dataset/verification provenance")
        if (
            not isinstance(manifest["frozen_at"], str)
            or datetime.fromisoformat(manifest["frozen_at"]).tzinfo is None
        ):
            raise ValueError("frozen_at needs a timezone")
        if (
            manifest["frozen"] is not True
            or manifest["qa_status"] != "VERIFIED"
            or not isinstance(manifest["records"], list)
            or not manifest["records"]
            or type(manifest["sample_count"]) is not int
            or manifest["sample_count"] != len(manifest["records"])
        ):
            raise ValueError("Manifest must be frozen, verified and complete")
        variants = _experiment(manifest, comparison, grouping)
        raw_protocol = manifest.get("raw_value_protocol")
        if raw_protocol not in (None, "selected-value-text-v1"):
            raise ValueError("Unsupported raw_value_protocol")
        prepared, seen, sample_ids = [], set(), set()
        for index, record in enumerate(manifest["records"]):
            gold = None
            try:
                if record["qa_status"] != "VERIFIED":
                    raise ValueError("Unverified record")
                gold = load_artifact(manifest_path.parent, record["gold"])
                evidence = load_artifact(manifest_path.parent, record["evidence"])
                validate_gold(gold, evidence, manifest)
                if gold["receipt_id"] in seen or gold["sample_id"] in sample_ids:
                    raise ValueError("Duplicate receipt/sample in manifest")
                seen.add(gold["receipt_id"])
                sample_ids.add(gold["sample_id"])
                if raw_protocol:
                    cells = list(gold["fields"].values()) + [
                        r[f] for r in gold["line_items"] for f in LINE_FIELDS
                    ]
                    if any(
                        c["annotation_status"] == "PRESENT"
                        and not isinstance(c["raw_value"], str)
                        for c in cells
                    ):
                        raise ValueError(
                            "Raw ablation needs QA printed strings for every PRESENT gold cell"
                        )
                oracle = None
                if "oracle_evidence" in record:
                    if record.get("oracle_qa_status") != "VERIFIED":
                        raise ValueError("Unverified oracle evidence")
                    oracle = load_artifact(
                        manifest_path.parent, record["oracle_evidence"]
                    )
                    real_blocks, oracle_blocks = flatten(evidence), flatten(oracle)
                    if (
                        oracle["receipt_id"] != evidence["receipt_id"]
                        or oracle["ocr_run_id"] != evidence["ocr_run_id"]
                        or [
                            (
                                b.block_id,
                                b.page,
                                b.reading_order,
                                b.polygon,
                                b.confidence,
                            )
                            for b in real_blocks
                        ]
                        != [
                            (
                                b.block_id,
                                b.page,
                                b.reading_order,
                                b.polygon,
                                b.confidence,
                            )
                            for b in oracle_blocks
                        ]
                    ):
                        raise ValueError(
                            "Oracle geometry/identity/confidence differs from real evidence"
                        )
                    real_pages = evidence.get("pages", [{"evidence": evidence}])
                    oracle_pages = oracle.get("pages", [{"evidence": oracle}])
                    if [p["evidence"]["engine"] for p in real_pages] != [
                        p["evidence"]["engine"] for p in oracle_pages
                    ]:
                        raise ValueError("Oracle engine differs from real evidence")
                prepared.append((record, evidence, gold, oracle))
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                ValidationError,
            ) as exc:
                report["failures"].append(
                    {
                        "record_index": index,
                        "stage": "eligibility",
                        "sample_id": gold.get("sample_id")
                        if isinstance(gold, dict)
                        else None,
                        "artifacts": record,
                        "reason": f"{type(exc).__name__}: {exc}",
                    }
                )
        report["coverage"]["eligible"] = len(prepared)
        if report["failures"]:
            raise ValueError(
                f"{len(report['failures'])}/{len(manifest['records'])} records failed eligibility; no extraction"
            )
        modes = {name: {"real": [], "oracle": []} for name in variants}
        for record, evidence, gold, oracle in prepared:
            sample = {
                "sample_id": gold["sample_id"],
                "receipt_id": gold["receipt_id"],
                "artifacts": record,
                "gold": gold,
                "variants": {},
            }
            failed = False
            for name in variants:
                sample["variants"][name] = {}
                for mode, source in (("real", evidence), ("oracle", oracle)):
                    if source is None:
                        continue
                    try:
                        run = uuid5(UUID(gold["receipt_id"]), VERSION + mode)
                        if name == BASELINE_GROUPING:
                            result = extract_invoice(
                                copy.deepcopy(source), kie_run_id=run
                            )
                        else:
                            result = extract_with_grouping(
                                copy.deepcopy(source), kie_run_id=run, grouping=name
                            )
                        modes[name][mode].append((result, gold))
                        # Only raw predictions on failure; scores are emitted once the
                        # entire paired run succeeds, never an undocumented subset.
                        sample["variants"][name][mode] = {"prediction": result}
                    except Exception as exc:
                        failed = True
                        report["failures"].append(
                            {
                                "sample_id": gold["sample_id"],
                                "stage": "extraction",
                                "grouping": name,
                                "mode": mode,
                                "reason": f"{type(exc).__name__}: {exc}",
                            }
                        )
            if not failed:
                report["coverage"]["processed"] += 1
            report["samples"].append(sample)
        if report["failures"]:
            raise ValueError(
                "Extraction failed; paired metrics withheld for the entire manifest"
            )
        summaries = {}
        for name in variants:
            real = metrics(modes[name]["real"])
            oracle = metrics(modes[name]["oracle"]) if modes[name]["oracle"] else None
            gap = None
            if len(modes[name]["oracle"]) == len(prepared):
                gap = {
                    f: (
                        oracle["headers"][f]["exact_match"]
                        - real["headers"][f]["exact_match"]
                        if real["headers"][f]["exact_match"] is not None
                        else None
                    )
                    for f in HEADER_FIELDS
                }
                real["error_taxonomy"]["OCR_PROPAGATION"] = sum(
                    known(g["fields"][f])
                    and correct(o["fields"][f], g["fields"][f])
                    and not correct(r["fields"][f], g["fields"][f])
                    for (r, g), (o, _) in zip(
                        modes[name]["real"], modes[name]["oracle"]
                    )
                    for f in HEADER_FIELDS
                )
            slices = {}
            for key in ("input_type", "template_id", "error_group"):
                buckets = {}
                for (record, _, gold, _), pair in zip(prepared, modes[name]["real"]):
                    label = record.get(key, gold.get(key)) or "UNSPECIFIED"
                    buckets.setdefault(str(label), []).append(pair)
                slices[key] = {
                    label: {"sample_count": len(pairs), "metrics": metrics(pairs)}
                    for label, pairs in buckets.items()
                }
            summaries[name] = {
                "configuration": dict(GROUPING_CONFIGURATIONS[name]),
                "extractor": dict(GROUPING_EXTRACTORS[name]),
                "metrics": real,
                "modes": {"real": real, "oracle": oracle},
                "mode_counts": {
                    mode: len(pairs) for mode, pairs in modes[name].items()
                },
                "propagation_gap": gap,
                "slices": slices,
            }
        for sample in report["samples"]:
            for name in variants:
                for mode, item in sample["variants"][name].items():
                    sample["variants"][name][mode] = _sample_result(
                        item["prediction"], sample["gold"], raw_protocol
                    )
        selected = summaries[variants[0]]
        report.update(
            status="COMPLETED",
            metrics=selected["metrics"],
            modes=selected["modes"],
            propagation_gap=selected["propagation_gap"],
            evaluated=len(prepared),
            variants=summaries,
            result_scope="synthetic_diagnostic"
            if manifest["synthetic"]
            else "frozen_module_evaluation",
        )
        if comparison:
            report["delta"] = _delta(
                summaries[BASELINE_GROUPING]["metrics"],
                summaries[INTERVAL_GROUPING]["metrics"],
            )
        report["coverage"].update(
            evaluated=len(prepared),
            fraction=ratio(len(prepared), manifest["sample_count"]),
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ValidationError,
        subprocess.CalledProcessError,
    ) as exc:
        report["reasons"].append(f"{type(exc).__name__}: {exc}")
        report["coverage"]["fraction"] = (
            ratio(0, report["coverage"]["required"])
            if type(report["coverage"]["required"]) is int
            else None
        )
    return report
