"""Frozen-manifest evaluator. Synthetic unit diagnostics are never thesis results."""

import hashlib
import json
import subprocess
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from . import extract_invoice
from .config import CONFIGURATION, EXTRACTOR, HEADER_FIELDS, LINE_FIELDS, MONEY_FIELDS
from .evidence import flatten

ROOT = Path(__file__).resolve().parents[3]
VERSION = "invoice-evaluation-2.0.0"
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


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def correct(prediction, gold):
    return (prediction["value_status"], prediction["normalized_value"]) == (
        gold["annotation_status"],
        gold["normalized_value"],
    )


def row_matches(predictions, gold):
    """One-to-one maximum overlap matching using annotated evidence, not values.

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


def metrics(pairs):
    fields = {}
    errors = Counter({key: 0 for key in TAXONOMY})
    for field in HEADER_FIELDS:
        count = Counter()
        for result, gold in pairs:
            p, g = result["fields"][field], gold["fields"][field]
            ok = correct(p, g)
            present, expected = (
                p["value_status"] == "PRESENT",
                g["annotation_status"] == "PRESENT",
            )
            count.update(
                total=1,
                correct=int(ok),
                predicted_present=int(present),
                gold_present=int(expected),
                true_positive=int(ok and expected),
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
            "exact_match": ratio(count["correct"], count["total"]),
            "precision": precision,
            "recall": recall,
            "f1": ratio(
                2 * count["true_positive"],
                count["predicted_present"] + count["gold_present"],
            ),
            "review_rate": ratio(count["review"], count["total"]),
        }
    totals = Counter()
    columns = Counter({f: 0 for f in LINE_FIELDS})
    for result, gold in pairs:
        predicted, expected = result["line_items"], gold["line_items"]
        matches = row_matches(predicted, expected)
        complete = 0
        for i, j in matches:
            matches_cells = [
                correct(predicted[j][f], expected[i][f]) for f in LINE_FIELDS
            ]
            columns.update({f: int(ok) for f, ok in zip(LINE_FIELDS, matches_cells)})
            complete += all(matches_cells)
            errors["COLUMN_ALIGNMENT_ERROR"] += sum(not ok for ok in matches_cells)
        full_header = all(
            correct(result["fields"][f], gold["fields"][f]) for f in HEADER_FIELDS
        )
        full_table = complete == len(expected) == len(predicted)
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
        )
        errors["ROW_DETECTION_ERROR"] += (
            len(expected) + len(predicted) - 2 * len(matches)
        )
        errors["CONSISTENCY_WARNING"] += sum(
            c["status"] == "WARNING" for c in result["consistency"]["checks"]
        )
    return {
        "headers": fields,
        "lines": {
            **totals,
            "detection_recall": ratio(totals["matched_rows"], totals["gold_rows"]),
            "extra_row_rate": ratio(totals["extra_rows"], totals["predicted_rows"]),
            "matched_row_cell_correctness": ratio(
                sum(columns.values()), totals["matched_rows"] * len(LINE_FIELDS)
            ),
            "per_column_correctness": {
                f: ratio(n, totals["matched_rows"]) for f, n in columns.items()
            },
            "complete_line_accuracy": ratio(
                totals["complete_rows"], totals["gold_rows"]
            ),
        },
        "complete_header_accuracy": ratio(
            totals["complete_header"], totals["documents"]
        ),
        "complete_table_accuracy": ratio(totals["complete_table"], totals["documents"]),
        "complete_invoice_accuracy": ratio(
            totals["complete_invoice"], totals["documents"]
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


def validate_gold(gold, evidence, manifest):
    schema = json.loads(
        (ROOT / "schemas/invoice-annotation.v2.schema.json").read_text()
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(gold)
    ids = {b.block_id for b in flatten(evidence)}
    if (
        gold["receipt_id"] != evidence["receipt_id"]
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
                and (cell["normalized_value"] is None or not cell["source_block_ids"])
            )
            or (
                cell["annotation_status"] != "PRESENT"
                and cell["normalized_value"] is not None
            )
        ):
            raise ValueError("Gold value/evidence invariant failed")
    for row in gold["line_items"]:
        if not any(row[f]["source_block_ids"] for f in LINE_FIELDS):
            raise ValueError("Gold row needs evidence for detection matching")
    named_cells = list(gold["fields"].items()) + [
        (f, r[f]) for r in gold["line_items"] for f in LINE_FIELDS
    ]
    for field, cell in named_cells:
        if cell["annotation_status"] != "PRESENT":
            continue
        value = cell["normalized_value"]
        if field in MONEY_FIELDS:
            valid = type(value) is int and value >= 0
        elif field == "quantity":
            valid = type(value) in (int, float) and value >= 0
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
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(
            str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0"
        )
    return digest.hexdigest()


def evaluate(manifest_path: Path):
    report = {
        "status": "WAITING_FOR_VERIFIED_V2_GOLD",
        "metrics": None,
        "modes": None,
        "propagation_gap": None,
        "evaluated": 0,
        "reasons": [],
        "evaluator_version": VERSION,
        "extractor": dict(EXTRACTOR),
        "configuration": dict(CONFIGURATION),
        "manifest": str(manifest_path),
        "git_commit": None,
        "git_dirty": None,
        "implementation_sha256": implementation_digest(),
    }
    try:
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
        report["manifest_sha256"] = hashlib.sha256(data).hexdigest()
        for key in (
            "dataset_family",
            "dataset_snapshot",
            "split",
            "synthetic",
            "template_regime",
        ):
            report[key] = manifest[key]
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
            or datetime.fromisoformat(
                manifest["frozen_at"].replace("Z", "+00:00")
            ).tzinfo
            is None
        ):
            raise ValueError("frozen_at needs a timezone")
        if (
            manifest["frozen"] is not True
            or manifest["qa_status"] != "VERIFIED"
            or not manifest["verified_by"]
            or not manifest["frozen_at"]
            or manifest["configuration"] != CONFIGURATION
            or not manifest["records"]
            or manifest["sample_count"] != len(manifest["records"])
        ):
            raise ValueError(
                "Manifest must be frozen, verified, complete and match this configuration"
            )
        prepared = []
        seen = set()
        for record in manifest["records"]:
            if record["qa_status"] != "VERIFIED":
                raise ValueError("Unverified record")
            gold = load_artifact(manifest_path.parent, record["gold"])
            evidence = load_artifact(manifest_path.parent, record["evidence"])
            validate_gold(gold, evidence, manifest)
            if gold["receipt_id"] in seen:
                raise ValueError("Duplicate receipt in manifest")
            seen.add(gold["receipt_id"])
            oracle = None
            if "oracle_evidence" in record:
                if record.get("oracle_qa_status") != "VERIFIED":
                    raise ValueError("Unverified oracle evidence")
                oracle = load_artifact(manifest_path.parent, record["oracle_evidence"])
                # Oracle keeps source geometry/IDs and only replaces verified text.
                real_blocks, oracle_blocks = flatten(evidence), flatten(oracle)
                if oracle["receipt_id"] != evidence["receipt_id"] or [
                    (b.block_id, b.page, b.polygon) for b in real_blocks
                ] != [(b.block_id, b.page, b.polygon) for b in oracle_blocks]:
                    raise ValueError(
                        "Oracle geometry/identity differs from real evidence"
                    )
            prepared.append((evidence, gold, oracle))
        # No extraction until every record has passed eligibility checks.
        modes = {"real": [], "oracle": []}
        for evidence, gold, oracle in prepared:
            for mode, source in (("real", evidence), ("oracle", oracle)):
                if source is not None:
                    run = uuid5(UUID(gold["receipt_id"]), VERSION + mode)
                    modes[mode].append((extract_invoice(source, kie_run_id=run), gold))
        real = metrics(modes["real"])
        oracle_metrics = metrics(modes["oracle"]) if modes["oracle"] else None
        report.update(
            status="COMPLETED",
            metrics=real,
            evaluated=len(prepared),
            modes={"real": real, "oracle": oracle_metrics},
            result_scope="synthetic_diagnostic"
            if manifest["synthetic"]
            else "frozen_module_evaluation",
        )
        if len(modes["oracle"]) == len(prepared):
            report["propagation_gap"] = {
                f: oracle_metrics["headers"][f]["exact_match"]
                - real["headers"][f]["exact_match"]
                for f in HEADER_FIELDS
            }
            real["error_taxonomy"]["OCR_PROPAGATION"] = sum(
                correct(o["fields"][f], g["fields"][f])
                and not correct(r["fields"][f], g["fields"][f])
                for (r, g), (o, _) in zip(modes["real"], modes["oracle"])
                for f in HEADER_FIELDS
            )
        return report
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
        return report
