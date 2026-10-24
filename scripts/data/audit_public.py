"""Audit prepared partial public data, including eligible-field masks and native provenance."""

import argparse
import json
from collections import Counter
from pathlib import Path
from PIL import Image
from jsonschema import Draft202012Validator, FormatChecker
from .common import HEADERS, LINE_FIELDS, ROOT, dump, read_csv, resolve, sha


def audit(root):
    root = Path(root).resolve()
    rows = read_csv(root / "manifest.csv")
    errors = []
    seen = set()
    headers = Counter()
    line_fields = Counter()
    native_geometry = 0
    schema = json.loads(
        (ROOT / "schemas/invoice-annotation.v2.schema.json").read_text()
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for row in rows:
        try:
            if row["sample_id"] in seen:
                raise ValueError("Duplicate canonical sample ID")
            seen.add(row["sample_id"])
            for path, checksum in (
                ("document_path", "document_sha256"),
                ("ground_truth_path", "ground_truth_sha256"),
                ("native_annotation_path", "native_annotation_sha256"),
            ):
                if sha(resolve(root, row[path])) != row[checksum]:
                    raise ValueError("Artifact checksum mismatch: " + path)
            with Image.open(resolve(root, row["document_path"])) as image:
                image.verify()
            gold = json.loads(
                resolve(root, row["ground_truth_path"]).read_text(encoding="utf-8")
            )
            validator.validate(gold)
            if gold["synthetic"] is not False or set(gold["fields"]) != set(HEADERS):
                raise ValueError("Public canonical contract mismatch")
            if (
                gold["sample_id"] != row["sample_id"]
                or gold["split"] != row["official_split"]
            ):
                raise ValueError("Identity/official split mismatch")
            if gold["mapping_version"] != row["mapping_version"]:
                raise ValueError("Mapping version mismatch")
            mask = set(json.loads(row["supported_fields"]))
            for name, c in gold["fields"].items():
                if c["annotation_status"] == "PRESENT":
                    if name not in mask:
                        raise ValueError("Present header missing from eligible mask")
                    headers[name] += 1
            for line in gold["line_items"]:
                for name in LINE_FIELDS:
                    if line[name]["annotation_status"] == "PRESENT":
                        if "line_items." + name not in mask:
                            raise ValueError(
                                "Present row cell missing from eligible mask"
                            )
                        line_fields[name] += 1
            native = json.loads(
                resolve(root, row["native_annotation_path"]).read_text(encoding="utf-8")
            )
            if isinstance(native, dict) and "words" in native and "bboxes" in native:
                if len(native["words"]) != len(native["bboxes"]):
                    raise ValueError("Native OCR words/box count mismatch")
                native_geometry += 1
        except Exception as exc:
            errors.append(
                dict(sample=row["sample_id"], reason=f"{type(exc).__name__}: {exc}")
            )
    return dict(
        status="PASS_AUTOMATED_ONLY" if not errors else "FAILED",
        samples=len(rows),
        errors=errors,
        split_counts=dict(Counter(r["split"] for r in rows)),
        header_present_counts=dict(headers),
        line_present_counts=dict(line_fields),
        native_ocr_geometry_samples=native_geometry,
        independent_review=False,
        final_evaluation=False,
        mask_policy="Only annotated supported cells; never score unavailable labels as extraction failures",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    a = p.parse_args()
    report = audit(a.root)
    dump(a.root / "qa.json", report)
    print(json.dumps(report, indent=2))
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
