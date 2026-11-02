"""Unscored paired header replay on TV2 development evidence; never gold QA."""

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.kie.v2 import extract_invoice, extract_with_layout
from ai.kie.v2.config import CONFIGURATION, LAYOUT_CONFIGURATION, HEADER_FIELDS


def inspect(root: Path, split: str) -> dict:
    manifest_path = root / f"{split}-manifest.json"
    data = manifest_path.read_bytes()
    manifest = json.loads(data)
    if manifest.get("split") != split or split not in {"train", "validation"}:
        raise ValueError("Only train/validation development evidence is permitted")
    records = manifest["records"]
    if manifest["sample_count"] != len(records):
        raise ValueError("Manifest count mismatch")
    changes = Counter()
    transitions = Counter()
    routes = Counter()
    changed_samples = 0
    seen = set()
    for record in records:
        sample_id = record["sample_id"]
        if sample_id in seen or record["split"] != split:
            raise ValueError("Duplicate sample or wrong split")
        seen.add(sample_id)
        reference = record["evidence"]
        path = (root / reference["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Evidence path escapes handoff root")
        evidence_bytes = path.read_bytes()
        if hashlib.sha256(evidence_bytes).hexdigest() != reference["sha256"]:
            raise ValueError("Evidence hash mismatch")
        evidence = json.loads(evidence_bytes)
        original = copy.deepcopy(evidence)
        run = uuid5(UUID(evidence["receipt_id"]), "header-layout-replay-0.1")
        baseline = extract_invoice(evidence, kie_run_id=run)
        layout = extract_with_layout(evidence, kie_run_id=run)
        if evidence != original:
            raise ValueError("Evidence changed during extraction")
        if (baseline["line_items"], baseline["tax_breakdown"]) != (
            layout["line_items"],
            layout["tax_breakdown"],
        ):
            raise ValueError("Header variant changed line items or tax groups")
        routes[record["source_type"]] += 1
        sample_changed = False
        for field in HEADER_FIELDS:
            before, after = baseline["fields"][field], layout["fields"][field]
            if (before["value_status"], before["normalized_value"]) != (
                after["value_status"],
                after["normalized_value"],
            ):
                changes[field] += 1
                transitions[
                    f"{field}:{before['value_status']}->{after['value_status']}"
                ] += 1
                sample_changed = True
        changed_samples += sample_changed
    return {
        "status": "UNSCORED_REPLAY",
        "gold_used": False,
        "metrics": None,
        "split": split,
        "manifest_sha256": hashlib.sha256(data).hexdigest(),
        "qa_status": manifest.get("qa_status"),
        "records": len(records),
        "processed": len(records),
        "routes": dict(sorted(routes.items())),
        "changed_samples": changed_samples,
        "changed_fields": dict(sorted(changes.items())),
        "status_transitions": dict(sorted(transitions.items())),
        "baseline_configuration": CONFIGURATION,
        "layout_configuration": LAYOUT_CONFIGURATION,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--split", required=True, choices=("train", "validation"))
    args = parser.parse_args()
    print(json.dumps(inspect(args.root, args.split), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
