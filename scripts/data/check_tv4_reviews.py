"""Check human review receipts against exact artifacts; never issue VERIFIED status."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from .common import dump, resolve, sha


def check(root):
    root = Path(root).resolve()
    intake = json.loads((root / "evaluation-intake.json").read_text(encoding="utf-8"))
    failures = []
    ready = 0
    for row in intake["review_records"]:
        reasons = []
        try:
            review = json.loads(
                resolve(root, row["review_path"]).read_text(encoding="utf-8")
            )
            if review["record_id"] != row["record_id"]:
                raise ValueError("Review identity mismatch")
            manifest = json.loads(
                (root / f"evaluator-{row['split']}-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            record = next(
                r for r in manifest["records"] if r["record_id"] == row["record_id"]
            )
            required = (
                "source",
                "source_gold",
                "source_regions",
                "source_row_regions",
                "evidence",
                "gold",
            )
            if set(review["artifact_hashes"]) != set(required):
                reasons.append("Missing source/evidence/gold hash bindings")
            for key, ref in review["artifact_hashes"].items():
                if (
                    ref != record.get(key)
                    or sha(resolve(root, ref["path"])) != ref["sha256"]
                ):
                    reasons.append("Changed or substituted artifact: " + key)
            reviewer = review.get("reviewed_by", "").strip()
            author = review.get("annotation_author", "").strip()
            if not reviewer or not author or reviewer.casefold() == author.casefold():
                reasons.append(
                    "Named independent reviewer and annotation author required"
                )
            when = review.get("reviewed_at")
            if not when or datetime.fromisoformat(when).tzinfo is None:
                reasons.append("Actual timezone-aware review date required")
            for field in (
                "independent_reviewer_confirmed",
                "source_gold_approved",
                "source_regions_approved",
                "source_rows_approved",
                "block_alignment_approved",
            ):
                if review.get(field) is not True:
                    reasons.append("Approval pending: " + field)
            if review.get("unresolved") or review.get("source_label_changes"):
                reasons.append(
                    "Unresolved findings or label changes need owner review; preserve original cohort"
                )
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
            reasons.append(str(exc))
        if reasons:
            failures.append(dict(record_id=row["record_id"], reasons=reasons))
        else:
            ready += 1
    return dict(
        status="REVIEW_RECEIPTS_COMPLETE"
        if not failures
        else "PENDING_INDEPENDENT_REVIEW",
        required=len(intake["review_records"]),
        review_receipts_complete=ready,
        failures=failures,
        grants_verified=False,
        note="Receipt validation cannot prove a human actually reviewed. Owner approval, semantic alignment validation and protocol/config sign-off remain required.",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError("Use a new report path")
    report = check(args.root)
    dump(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, indent=2))
    return 2 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
