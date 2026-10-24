"""Prepare exact TV4 A/B manifests and hash-bound human review forms; never grant QA."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .common import dump, resolve, sha
from .verify_tv4_handoff import verify


def prepare(root, runtime, output):
    root, runtime, output = map(lambda p: Path(p).resolve(), (root, runtime, output))
    if output.exists() or output.is_relative_to(root):
        raise ValueError("Output must be a new directory outside the source package")
    integrity = verify(root)
    if integrity["errors"]:
        raise ValueError("Source package failed integrity")
    experiment = json.loads(
        subprocess.check_output(
            [
                sys.executable,
                "-X",
                "utf8",
                str(runtime / "scripts/evaluate_invoice_kie.py"),
                "--print-experiment",
            ],
            cwd=runtime,
            text=True,
            encoding="utf-8",
        )
    )
    from jsonschema import Draft202012Validator

    schema_path = runtime / "schemas/invoice-kie-experiment.v1.schema.json"
    Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8"))).validate(
        experiment
    )
    shutil.copytree(root, output)
    dump(output / "experiment.json", experiment)
    review_rows = []
    for split in ("train", "validation"):
        candidate = json.loads(
            (root / f"{split}-manifest.json").read_text(encoding="utf-8")
        )
        manifest = dict(candidate)
        manifest.update(
            schema_version="tv2-evaluator-intake-0.1",
            template_regime="template-disjoint-development",
            configuration=experiment["configurations"]["geometry_grouping_v2"],
            experiment=experiment,
            experiment_approval="PENDING_TV1_TV4_SIGN_OFF",
            frozen_at=json.loads(
                (root / "selection-freeze.json").read_text(encoding="utf-8")
            )["created_at"],
            qa_status="PENDING_REVIEW",
            verified_by="",
            final_eligible=False,
        )
        for record in manifest["records"]:
            record["qa_status"] = "PENDING_REVIEW"
            refs = {
                key: dict(record[key])
                for key in (
                    "source",
                    "source_gold",
                    "source_regions",
                    "source_row_regions",
                    "evidence",
                    "gold",
                )
                if key in record
            }
            for ref in refs.values():
                if sha(resolve(root, ref["path"])) != ref["sha256"]:
                    raise ValueError("Changed artifact")
            review = dict(
                record_id=record["record_id"],
                reviewed_by="",
                reviewed_at="",
                annotation_author="",
                independent_reviewer_confirmed=False,
                source_gold_approved=False,
                source_regions_approved=False,
                source_rows_approved=False,
                block_alignment_approved=False,
                artifact_hashes=refs,
                source_label_changes=[],
                unresolved=[],
                note="Human review required. Source truth must not be changed to match OCR. Keep every record, including failures; no automatic VERIFIED promotion.",
            )
            review_path = f"reviews/{record['record_id']}.json"
            dump(output / review_path, review)
            review_rows.append(
                dict(
                    record_id=record["record_id"],
                    split=split,
                    review_path=review_path,
                    qa_status="PENDING_REVIEW",
                )
            )
        dump(output / f"evaluator-{split}-manifest.json", manifest)
    report = dict(
        status="PREPARED_PENDING_INDEPENDENT_REVIEW",
        sample_count=len(review_rows),
        experiment=experiment,
        experiment_schema_sha256=sha(schema_path),
        evaluator_sha256=sha(runtime / "scripts/evaluate_invoice_kie.py"),
        original_package_modified=False,
        qa_promoted=False,
        review_records=review_rows,
        note="Membership freeze is not reviewed gold. Scored A/B must remain blocked until actual review and protocol/config sign-off.",
    )
    dump(output / "evaluation-intake.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "runtime", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.root, args.runtime, args.output)
    print(
        json.dumps({k: v for k, v in report.items() if k != "review_records"}, indent=2)
    )


if __name__ == "__main__":
    main()
