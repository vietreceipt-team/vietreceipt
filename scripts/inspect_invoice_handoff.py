"""Inspect TV2 train/validation candidate artifacts and run unscored KIE A/B.

Never grants VERIFIED, edits source labels, or computes accuracy on candidates.
Exit 2 means intact/processed but waiting for human QA; exit 1 means a failure.
"""

import argparse
import copy
import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.kie.v2 import extract_with_grouping
from jsonschema import ValidationError

from ai.kie.v2.config import BASELINE_GROUPING, GROUPING_CONFIGURATIONS, LINE_FIELDS
from ai.kie.v2.evaluation import (
    ROOT,
    VERSION,
    evaluate,
    implementation_digest,
    load_artifact,
    validate_gold,
)
from ai.kie.v2.source_evaluation import validate_regions


def read_reference(root, reference, *, as_json=True):
    path = (root / reference["path"]).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Artifact escapes package root")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != reference["sha256"]:
        raise ValueError("Artifact checksum mismatch: " + reference["path"])
    return load_artifact(root, reference) if as_json else data


def inspect(root, output, source_revision):
    root = root.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "WAITING_FOR_VERIFIED_V2_GOLD",
        "metrics": None,
        "scope": "unscored_candidate_inspection; not accuracy or independent QA",
        "source_revision": source_revision,
        "implementation_sha256": implementation_digest(),
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "git_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        ),
        "evaluator_version": VERSION,
        "configurations": copy.deepcopy(GROUPING_CONFIGURATIONS),
        "required": 0,
        "eligible_for_accuracy": 0,
        "reader_success": 0,
        "reader_failed": 0,
        "kie_paired_success": 0,
        "failures": [],
        "records": [],
        "manifest_sha256": {},
        "qa_status": "PENDING_REVIEW",
        "grants_verified": False,
        "final_test_opened": False,
    }
    prepared, seen = [], set()
    partitions = {
        k: defaultdict(set)
        for k in ("base_document_id", "template_id", "source_sha256")
    }
    try:
        for split in ("train", "validation"):
            manifest_path = root / f"{split}-manifest.json"
            raw = manifest_path.read_bytes()
            manifest = json.loads(raw)
            report["manifest_sha256"][split] = hashlib.sha256(raw).hexdigest()
            if (
                manifest["schema_version"] != "tv2-tv4-handoff-candidate-0.1"
                or manifest["split"] != split
                or manifest["qa_status"] != "PENDING_REVIEW"
                or manifest["frozen"] is not True
                or manifest["synthetic"] is not True
                or type(manifest["sample_count"]) is not int
                or manifest["sample_count"] != len(manifest["records"])
            ):
                raise ValueError(
                    "Invalid candidate schema/split/QA/count; inspection accepts pending development only"
                )
            report["required"] += len(manifest["records"])
            # Preserve the formal gate result on the original, unmodified manifest.
            gate = evaluate(manifest_path, comparison=True)
            (output / f"{split}-formal-gate.json").write_text(
                json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            for record in manifest["records"]:
                sid = record.get("record_id")
                try:
                    if (
                        not isinstance(sid, str)
                        or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", sid)
                        or sid in seen
                        or record["split"] != split
                        or record.get("final_eligible") not in (False, "false")
                        or record["qa_status"] != "PENDING_REVIEW"
                    ):
                        raise ValueError(
                            "Duplicate/unsafe/final/wrong-split record or changed QA"
                        )
                    seen.add(sid)
                    for key in partitions:
                        value = (
                            record["source"]["sha256"]
                            if key == "source_sha256"
                            else record[key]
                        )
                        if not isinstance(value, str) or not value:
                            raise ValueError("Missing split identity")
                        partitions[key][value].add(split)
                    read_reference(root, record["source"], as_json=False)
                    source_gold = read_reference(root, record["source_gold"])
                    validate_gold(source_gold, None, manifest, aligned=False)
                    if (
                        source_gold["receipt_id"] != record["source_receipt_id"]
                        or source_gold["sample_id"] != record["original_sample_id"]
                    ):
                        raise ValueError("Source identity alias mismatch")
                    read_reference(root, record["source_regions"])
                    regions = read_reference(root, record["source_row_regions"])
                    validate_regions(regions, source_gold)
                    summary = {
                        "record_id": sid,
                        "split": split,
                        "base_document_id": record["base_document_id"],
                        "template_id": record["template_id"],
                        "input_type": record["source_type"],
                        "augmentation_type": record["augmentation_type"],
                        "qa_status": record["qa_status"],
                        "source_gold_rows_unreviewed": len(source_gold["line_items"]),
                        "source": record["source"],
                        "source_gold": record["source_gold"],
                        "source_row_regions": record["source_row_regions"],
                        "variants": {},
                    }
                    report["records"].append(summary)
                    if record["reader_status"] != "SUCCESS":
                        report["reader_failed"] += 1
                        report["failures"].append(
                            {
                                "record_id": sid,
                                "stage": "reader",
                                "reason": record.get("reader_error", "Reader failed"),
                            }
                        )
                        continue
                    evidence = read_reference(root, record["evidence"])
                    gold = read_reference(root, record["gold"])
                    validate_gold(gold, evidence, manifest)
                    if (
                        evidence["receipt_id"] != record["receipt_id"]
                        or evidence["ocr_run_id"] != record["reader_run_id"]
                        or gold["sample_id"] != sid
                    ):
                        raise ValueError("Evidence/aligned identity alias mismatch")
                    comparable = copy.deepcopy(gold)
                    comparable.update(
                        receipt_id=source_gold["receipt_id"],
                        sample_id=source_gold["sample_id"],
                    )
                    cells = list(comparable["fields"].values()) + [
                        row[f] for row in comparable["line_items"] for f in LINE_FIELDS
                    ]
                    for cell in cells:
                        cell["source_block_ids"] = []
                    if comparable != source_gold:
                        raise ValueError(
                            "Candidate gold changed source values/statuses"
                        )
                    for key in ("reader_log", "reader_metadata"):
                        read_reference(root, record[key], as_json=False)
                    summary.update(
                        evidence=record["evidence"], candidate_gold=record["gold"]
                    )
                    report["reader_success"] += 1
                    prepared.append((summary, evidence))
                except (
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                    ValidationError,
                ) as exc:
                    report["failures"].append(
                        {
                            "record_id": sid,
                            "stage": "integrity",
                            "reason": f"{type(exc).__name__}: {exc}",
                        }
                    )
        if any(
            len(splits) > 1
            for groups in partitions.values()
            for splits in groups.values()
        ):
            raise ValueError("Source/base/template leakage across splits")
        report["base_documents"] = len(partitions["base_document_id"])
        report["templates"] = len(partitions["template_id"])
        # Integrity failures withhold all extraction. Reader failures remain in the
        # intended cohort; intact evidence may still be inspected without scores.
        if any(f["stage"] == "integrity" for f in report["failures"]):
            raise ValueError("Integrity errors; no extraction performed")
        for summary, evidence in prepared:
            outputs = {}
            for name in GROUPING_CONFIGURATIONS:
                try:
                    run = uuid5(
                        UUID(evidence["receipt_id"]), "kie49-candidate-inspection-1"
                    )
                    prediction = extract_with_grouping(
                        copy.deepcopy(evidence), kie_run_id=run, grouping=name
                    )
                    destination = output / "predictions" / summary["record_id"]
                    destination.mkdir(parents=True, exist_ok=True)
                    path = destination / (name + ".json")
                    data = (
                        json.dumps(prediction, ensure_ascii=False, indent=2) + "\n"
                    ).encode()
                    path.write_bytes(data)
                    summary["variants"][name] = {
                        "prediction": str(path.relative_to(output)),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "predicted_rows": len(prediction["line_items"]),
                        "header_present": sum(
                            c["value_status"] == "PRESENT"
                            for c in prediction["fields"].values()
                        ),
                        "consistency_warnings": sum(
                            c["status"] == "WARNING"
                            for c in prediction["consistency"]["checks"]
                        ),
                    }
                    outputs[name] = prediction
                except Exception as exc:
                    report["failures"].append(
                        {
                            "record_id": summary["record_id"],
                            "stage": "kie",
                            "variant": name,
                            "reason": f"{type(exc).__name__}: {exc}",
                        }
                    )
            if len(outputs) == len(GROUPING_CONFIGURATIONS):
                report["kie_paired_success"] += 1
                baseline = outputs[BASELINE_GROUPING]
                summary["grouping_outputs_identical"] = all(
                    p["line_items"] == baseline["line_items"] for p in outputs.values()
                )
    except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
        report["failures"].append(
            {"stage": "package", "reason": f"{type(exc).__name__}: {exc}"}
        )
    report["counts_by_input"] = dict(
        Counter(r["input_type"] for r in report["records"])
    )
    report["failures_by_stage"] = dict(Counter(f["stage"] for f in report["failures"]))
    if report["failures"]:
        report["inspection_status"] = "FAILURES_RETAINED"
    else:
        report["inspection_status"] = "PASS_INTEGRITY_AND_KIE_CONTRACT_ONLY"
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output / "samples.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "sample_id",
                "split",
                "base_document_id",
                "input_type",
                "qa_status",
                "variant",
                "predicted_rows",
                "source_gold_rows_unreviewed",
                "accuracy",
            ]
        )
        for row in report["records"]:
            for name in GROUPING_CONFIGURATIONS:
                writer.writerow(
                    [
                        row["record_id"],
                        row["split"],
                        row["base_document_id"],
                        row["input_type"],
                        row["qa_status"],
                        name,
                        row["variants"].get(name, {}).get("predicted_rows"),
                        row["source_gold_rows_unreviewed"],
                        "",
                    ]
                )
    with (output / "failures.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["record_id", "stage", "variant", "reason"]
        )
        writer.writeheader()
        writer.writerows(report["failures"])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    report = inspect(args.root, args.output, args.source_revision)
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "records"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if report["failures"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
