#!/usr/bin/env python3
"""Prepare and validate the human-gated W3 OCR+KIE gold workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.kie.gold_workflow import (
    MANIFEST_PATH,
    create_adjudication_forms,
    paths_for,
    pending_manifest,
    prepare_workspace,
    promote_verified_manifest,
    sample_gate_errors,
    sha256,
    split_rows,
    workflow_status,
)


def _write_pending_manifest() -> bool:
    current = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if current.get("records"):
        return False
    MANIFEST_PATH.write_text(
        json.dumps(
            pending_manifest(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "prepare",
        help="create blank A/B forms and PENDING Oracle drafts without overwrite",
    )
    compare = subparsers.add_parser(
        "compare",
        help="compare completed A/B and create final/adjudication drafts",
    )
    compare.add_argument("test_id", choices=[row["test_id"] for row in split_rows()])
    oracle_hash = subparsers.add_parser(
        "oracle-hash",
        help="print the finalized Oracle SHA-256 to copy into its human QA form",
    )
    oracle_hash.add_argument(
        "test_id", choices=[row["test_id"] for row in split_rows()]
    )
    status = subparsers.add_parser(
        "status",
        help="show all reasons samples are not yet gold-ready",
    )
    status.add_argument("--test-id", choices=[row["test_id"] for row in split_rows()])
    subparsers.add_parser(
        "validate",
        help="strictly require all 40 samples and manifest to be VERIFIED",
    )
    promote = subparsers.add_parser(
        "promote-manifest",
        help="set manifest VERIFIED only after all explicit human records pass",
    )
    promote.add_argument("--annotation-provenance", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        result = prepare_workspace()
        result["pending_manifest_initialized"] = int(_write_pending_manifest())
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "compare":
        disagreements = create_adjudication_forms(args.test_id)
        print(
            json.dumps(
                {
                    "test_id": args.test_id,
                    "disagreement_fields": disagreements,
                    "next": "fill final annotation metadata and every adjudication decision",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "oracle-hash":
        sample = paths_for(args.test_id)
        print(
            json.dumps(
                {
                    "test_id": args.test_id,
                    "oracle_ocr_path": str(sample.oracle_ocr),
                    "oracle_sha256": sha256(sample.oracle_ocr),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "promote-manifest":
        manifest = promote_verified_manifest(args.annotation_provenance)
        print(
            json.dumps(
                {
                    "annotation_qa_state": manifest["annotation_qa_state"],
                    "records": len(manifest["records"]),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "status" and args.test_id:
        errors = sample_gate_errors(args.test_id)
        print(
            json.dumps(
                {"test_id": args.test_id, "ready": not errors, "reasons": errors},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    report = workflow_status()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.command == "validate" and report["pending"]:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
