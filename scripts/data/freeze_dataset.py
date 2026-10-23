"""Create an immutable, reviewed test inventory; never promote development data silently."""

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from .common import dump, read_csv, resolve, sha
from .validate_ground_truth import audit


def freeze(manifest, root, review, output):
    root = Path(root).resolve()
    output = Path(output)
    if output.exists():
        raise ValueError("Frozen inventory already exists; increment the version")
    qa = audit(manifest, root)
    if qa["status"] != "PASSED":
        raise ValueError("Dataset QA failed")
    if review.get("manifest_sha256") != sha(manifest):
        raise ValueError("Review refers to another manifest")
    for k in (
        "reviewed_by",
        "configuration_commit",
        "dataset_version",
        "frozen_at",
        "protocol",
    ):
        if not isinstance(review.get(k), str) or not review[k].strip():
            raise ValueError("Missing review: " + k)
    if datetime.fromisoformat(review["frozen_at"]).tzinfo is None:
        raise ValueError("Use timezone-aware frozen_at")
    if review.get("used_for_tuning") is not False:
        raise ValueError("Final data must not have been used for tuning")
    if review.get("independent_review") is not True:
        raise ValueError("Independent review is required")
    rows = read_csv(manifest)
    if any(r["split"] != "test" for r in rows):
        raise ValueError("Final inventory must contain test only")
    if {r["dataset_version"] for r in rows} != {review["dataset_version"]}:
        raise ValueError("Dataset version mismatch")
    if any(r.get("final_eligible") != "true" for r in rows):
        raise ValueError("Development-only records cannot be frozen")
    commit = subprocess.check_output(
        ["git", "rev-parse", review["configuration_commit"] + "^{commit}"], text=True
    ).strip()
    records = []
    for row in rows:
        record = dict(row)
        for col in ("document_path", "ground_truth_path", "transcript_path"):
            if row.get(col):
                record[col + "_sha256"] = sha(resolve(root, row[col]))
        records.append(record)
    inventory = dict(
        kind="dataset_inventory_not_kie_evaluation_manifest",
        frozen=True,
        review=review,
        configuration_commit=commit,
        manifest_sha256=sha(manifest),
        sample_count=len(records),
        base_sample_count=len({r["sample_id"] for r in records}),
        records=records,
        qa=qa,
    )
    dump(output, inventory)
    return inventory


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for k in ("manifest", "root", "review", "output"):
        p.add_argument("--" + k, type=Path, required=True)
    a = p.parse_args()
    freeze(a.manifest, a.root, json.loads(a.review.read_text()), a.output)


if __name__ == "__main__":
    main()
