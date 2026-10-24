"""Preserve rejected public records and source images separately, without relabeling."""

import argparse
import json
import shutil
from pathlib import Path

from .common import dump, resolve, sha, write_csv


def quarantine(input_path, source_root, report_path, output):
    input_path, source_root, report_path, output = map(
        Path, (input_path, source_root, report_path, output)
    )
    if output.exists():
        raise ValueError("Use a new quarantine directory")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if sha(input_path) != report["input_sha256"]:
        raise ValueError("Rejection report belongs to a different native export")
    raw_lines = input_path.read_bytes().splitlines(keepends=True)
    lines = [line.decode("utf-8") for line in raw_lines]
    rejected = report["rejected"]
    indexes = [r["line"] for r in rejected]
    if len(set(indexes)) != len(indexes) or any(
        type(i) is not int or i < 1 or i > len(lines) for i in indexes
    ):
        raise ValueError("Invalid or duplicate rejected source line")
    if report["usable_samples"] + len(rejected) != sum(bool(s.strip()) for s in lines):
        raise ValueError("Mapped/rejected counts do not account for the input cohort")
    output.mkdir(parents=True)
    rows = []
    for rejection in rejected:
        number = rejection["line"]
        folder = output / f"line-{number:06d}"
        folder.mkdir()
        # Preserve the actual exported line, including native labels, even if invalid JSON.
        (folder / "native-record.jsonl").write_bytes(raw_lines[number - 1])
        row = dict(
            family=report["family"],
            snapshot=report["snapshot"],
            mapping_version=report["mapping_version"],
            source_line=number,
            original_sample_id="",
            split="",
            reason=rejection["error"],
            native_record_path=f"{folder.name}/native-record.jsonl",
            native_record_sha256=sha(folder / "native-record.jsonl"),
            source_image_path="",
            source_image_sha256="",
            source_retention_error="",
            disposition="QUARANTINED_NOT_MAPPED",
            final_eligible=False,
        )
        try:
            native = json.loads(lines[number - 1])
            row["original_sample_id"] = str(native["id"])
            row["split"] = native["split"]
            image = resolve(source_root, native["image_path"])
            target = folder / ("source" + image.suffix.lower())
            shutil.copyfile(image, target)
            row["source_image_path"] = f"{folder.name}/{target.name}"
            row["source_image_sha256"] = sha(target)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            row["source_retention_error"] = str(exc)
        dump(folder / "rejection.json", row)
        rows.append(row)
    if rows:
        write_csv(output / "quarantine-manifest.csv", rows)
    summary = dict(
        family=report["family"],
        snapshot=report["snapshot"],
        source=report["source"],
        license_access=report["license_access"],
        mapping_version=report["mapping_version"],
        input_sha256=sha(input_path),
        rejection_report_sha256=sha(report_path),
        native_records=sum(bool(s.strip()) for s in lines),
        mapped_records=report["usable_samples"],
        quarantined_records=len(rows),
        images_retained=sum(bool(r["source_image_sha256"]) for r in rows),
        retention_failures=sum(bool(r["source_retention_error"]) for r in rows),
        label_changes=False,
        gold_generated=False,
        qa_status="PENDING_OWNER_REVIEW",
        records=rows,
    )
    dump(output / "quarantine-report.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "source-root", "report", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    summary = quarantine(args.input, args.source_root, args.report, args.output)
    print(json.dumps({k: v for k, v in summary.items() if k != "records"}, indent=2))
    return 2 if summary["retention_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
