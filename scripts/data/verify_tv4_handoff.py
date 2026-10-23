"""Integrity and leakage gate for a pending-review TV2/TV4 handoff; never grants VERIFIED."""

import argparse
import copy
import json
import math
from collections import defaultdict
from pathlib import Path
from .common import dump, resolve, sha


def verify(root):
    root = Path(root).resolve()
    errors = []
    seen = set()
    bases = defaultdict(set)
    templates = defaultdict(set)
    hashes = defaultdict(set)
    counts = dict(total_sources=0, reader_success=0, reader_failed=0)
    for split in ("train", "validation"):
        manifest = json.loads(
            (root / f"{split}-manifest.json").read_text(encoding="utf-8")
        )
        if manifest["split"] != split or manifest["sample_count"] != len(
            manifest["records"]
        ):
            errors.append("Manifest split/count mismatch")
        if manifest.get("qa_status") != "PENDING_REVIEW":
            errors.append("Review state changed without owner approval")
        for r in manifest["records"]:
            counts["total_sources"] += 1
            sid = r["record_id"]
            if sid in seen:
                errors.append("Duplicate record " + sid)
            seen.add(sid)
            if r["split"] != split or r["split"] == "test":
                errors.append("Unexpected split " + sid)
            bases[r["base_document_id"]].add(split)
            templates[r["template_id"]].add(split)
            hashes[r["source"]["sha256"]].add(split)
            try:
                for key in (
                    "source",
                    "source_gold",
                    "source_regions",
                    "source_row_regions",
                ):
                    artifact = resolve(root, r[key]["path"])
                    if sha(artifact) != r[key]["sha256"]:
                        errors.append("Artifact checksum mismatch " + sid + " " + key)
                original = json.loads(
                    resolve(root, r["source_gold"]["path"]).read_text(encoding="utf-8")
                )
                regions = json.loads(
                    resolve(root, r["source_regions"]["path"]).read_text(
                        encoding="utf-8"
                    )
                )
                expected = {
                    "fields." + k
                    for k, c in original["fields"].items()
                    if c["annotation_status"] == "PRESENT"
                }
                expected |= {
                    f"line_items.{i}.{k}"
                    for i, line in enumerate(original["line_items"])
                    for k in ("description", "unit", "quantity", "unit_price", "amount")
                    if line[k]["annotation_status"] == "PRESENT"
                }
                if {item["cell"] for item in regions} != expected:
                    errors.append("Missing/extra source cell regions " + sid)
                for region in regions:
                    b = region["bounds"]
                    if (
                        len(b) != 4
                        or not all(
                            type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1
                            for n in b
                        )
                        or b[0] >= b[2]
                        or b[1] >= b[3]
                    ):
                        errors.append("Invalid normalized source region " + sid)
                row_regions = json.loads(
                    resolve(root, r["source_row_regions"]["path"]).read_text(
                        encoding="utf-8"
                    )
                )
                if {item["line_id"] for item in row_regions} != {
                    line["line_id"] for line in original["line_items"]
                }:
                    errors.append("Missing/extra source row regions " + sid)
                if r["reader_status"] == "SUCCESS":
                    counts["reader_success"] += 1
                    for key in ("gold", "evidence"):
                        if sha(resolve(root, r[key]["path"])) != r[key]["sha256"]:
                            errors.append("Derived checksum mismatch " + sid)
                    evidence = json.loads(
                        resolve(root, r["evidence"]["path"]).read_text(encoding="utf-8")
                    )
                    from ai.document_reader.contract import validate_document

                    validate_document(evidence)
                    gold = json.loads(
                        resolve(root, r["gold"]["path"]).read_text(encoding="utf-8")
                    )
                    if (
                        evidence["receipt_id"] != r["receipt_id"]
                        or gold["receipt_id"] != r["receipt_id"]
                    ):
                        errors.append("Receipt alias mismatch " + sid)
                    ids = {
                        b["block_id"]
                        for p in evidence["pages"]
                        for b in p["evidence"]["blocks"]
                    }
                    comparable = copy.deepcopy(gold)
                    comparable["receipt_id"] = original["receipt_id"]
                    if gold["sample_id"] != r["record_id"]:
                        errors.append("Variant sample identity mismatch " + sid)
                    comparable["sample_id"] = original["sample_id"]
                    cells = list(comparable["fields"].values()) + [
                        i[k]
                        for i in comparable["line_items"]
                        for k in (
                            "description",
                            "unit",
                            "quantity",
                            "unit_price",
                            "amount",
                        )
                    ]
                    for c in cells:
                        if not set(c["source_block_ids"]) <= ids:
                            errors.append("Invented block ID " + sid)
                        c["source_block_ids"] = []
                    if comparable != original:
                        errors.append("Source gold values/statuses changed " + sid)
                else:
                    counts["reader_failed"] += 1
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(sid + ": " + str(exc))
    for kind, groups in (("base", bases), ("template", templates), ("content", hashes)):
        if any(len(s) > 1 for s in groups.values()):
            errors.append(kind + " crosses splits")
    return dict(
        status="PASS_INTEGRITY_ONLY" if not errors else "FAILED",
        errors=errors,
        counts=counts,
        independent_base_documents=len(bases),
        qa_status="PENDING_REVIEW",
        grants_verified=False,
        final_test_included=False,
        scope="Artifact bytes, source preservation, real block IDs, counts and split leakage only",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    a = p.parse_args()
    report = verify(a.root)
    dump(a.root / "integrity-report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
