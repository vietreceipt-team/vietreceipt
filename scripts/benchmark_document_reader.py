"""Reproducible manifest-driven reader diagnostics; no random split or test tuning."""

import argparse
import csv
import hashlib
import json
import mimetypes
import platform
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import jiwer

from ai.document_reader import DocumentReader, ReaderConfig, ReaderError


def dump(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def load_manifest(manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = manifest["samples"]
    if not samples or len({s["id"] for s in samples}) != len(samples):
        raise ValueError("Manifest must contain unique sample IDs")
    for sample in samples:
        if not sample["id"] or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in sample["id"]
        ):
            raise ValueError("Unsafe sample ID")
        source = (manifest_path.parent / sample["path"]).resolve()
        if not source.is_relative_to(manifest_path.parent.resolve()):
            raise ValueError("Sample path escapes manifest directory")
        expected_hash = sample.get("input_sha256")
        if expected_hash and hashlib.sha256(source.read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"Input checksum mismatch: {sample['id']}")
    if not manifest.get("dataset") or not manifest.get("version") or not manifest.get("split"):
        raise ValueError("Manifest requires dataset, version and split")
    return manifest


def benchmark(manifest_path, output, config, *, reader_factory=None):
    manifest = load_manifest(manifest_path)
    samples = manifest["samples"]
    output.mkdir(parents=True, exist_ok=False)
    (output / "predictions").mkdir()
    reader = (reader_factory or DocumentReader)(config=config)
    packages = {}
    for package in (
        "paddleocr",
        "paddlepaddle",
        "paddlex",
        "pypdfium2",
        "Pillow",
        "numpy",
        "jiwer",
    ):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    )
    dump(output / "manifest.json", manifest)
    dump(
        output / "config.json",
        {
            "config": config.__dict__,
            "packages": packages,
            "git_commit": git.stdout.strip() if git.returncode == 0 else "unavailable",
            "git_dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
            "source_sha256": {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in (Path("ai/document_reader"), Path("ai/ocr"), Path("scripts"))
                for p in sorted(folder.glob("*.py"))
            },
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "timing_policy": "serial, includes lazy model initialization on first OCR call; inspect cold_start_candidate",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "ocr_model": "PP-OCRv3",
            "orientation_model": "PP-LCNet_x1_0_doc_ori"
            if config.orientation == "auto"
            else None,
            "use_textline_orientation": False,
            "language": "vi",
            "metric_policy": "micro CER/WER; collapse whitespace only; failed reads scored as empty predictions when reference exists",
        },
    )
    dump(output / "inputs.json", [
        {"id": s["id"], "path": s["path"], "sha256":
         hashlib.sha256((manifest_path.parent / s["path"]).read_bytes()).hexdigest()
         if (manifest_path.parent / s["path"]).is_file() else None}
        for s in samples
    ])
    ocr_seen = False
    rows, aggregates = (
        [],
        defaultdict(
            lambda: {
                "char_errors": 0,
                "chars": 0,
                "word_errors": 0,
                "words": 0,
                "referenced": 0,
                "failures": 0,
                "samples": 0,
            }
        ),
    )
    for sample in samples:
        source = manifest_path.parent / sample["path"]
        row = {
            "id": sample["id"],
            "condition": sample.get("condition", "unspecified"),
            "status": "ok",
            "error": "",
            "cer": None,
            "wer": None,
            "duration_ms": None,
            "char_deletions": None,
            "char_substitutions": None,
            "char_insertions": None,
            "reference_chars": None,
            "cold_start_candidate": False,
        }
        predicted = ""
        started = time.perf_counter()
        try:
            data = source.read_bytes()
            row["input_sha256"] = hashlib.sha256(data).hexdigest()
            receipt_id = sample.get("receipt_id") or uuid5(
                NAMESPACE_URL, f"{manifest['dataset']}:{manifest['version']}:{sample['id']}:{row['input_sha256']}"
            )
            evidence, metadata = reader.process_with_metadata(
                data,
                content_type=mimetypes.guess_type(source)[0],
                receipt_id=receipt_id,
                ocr_run_id=uuid4(),
            )
            dump(output / "predictions" / (sample["id"] + ".json"), evidence)
            dump(
                output / "predictions" / (sample["id"] + ".metadata.json"),
                dict(metadata, input_sha256=hashlib.sha256(data).hexdigest()),
            )
            predicted = " ".join(
                b["text"] for p in evidence["pages"] for b in p["evidence"]["blocks"]
            )
            row["duration_ms"] = metadata["duration_ms"]
            has_ocr = any(p["source"] != "PDF_TEXT" for p in metadata["pages"])
            row["cold_start_candidate"] = has_ocr and not ocr_seen
            ocr_seen |= has_ocr
            if sample.get("expected_error"):
                row.update(
                    status="unexpected_success", error="Expected failure did not occur"
                )
        except (ReaderError, OSError) as exc:
            code = getattr(exc, "code", "INPUT_IO_FAILED")
            row.update(
                status="expected_failure"
                if sample.get("expected_error") == code
                else "failed",
                error=code,
            )
        row["wall_duration_ms"] = (time.perf_counter() - started) * 1000
        row.setdefault("input_sha256", None)
        reference = sample.get("reference")
        counts = None
        if reference is not None and reference.strip():
            ref, hyp = " ".join(reference.split()), " ".join(predicted.split())
            c, w = jiwer.process_characters(ref, hyp), jiwer.process_words(ref, hyp)
            row.update(cer=c.cer, wer=w.wer, char_deletions=c.deletions,
                       char_substitutions=c.substitutions, char_insertions=c.insertions,
                       reference_chars=len(ref))
            counts = (
                c.substitutions + c.deletions + c.insertions,
                len(ref),
                w.substitutions + w.deletions + w.insertions,
                len(ref.split()),
            )
        for key in ("all", row["condition"]):
            a = aggregates[key]
            a["samples"] += 1
            a["failures"] += row["status"] == "failed"
            if counts:
                a["referenced"] += 1
                for field, value in zip(
                    ("char_errors", "chars", "word_errors", "words"), counts
                ):
                    a[field] += value
        rows.append(row)
        print(
            f"{row['id']}: {row['status']} CER={row['cer']} WER={row['wer']}",
            flush=True,
        )
    for a in aggregates.values():
        a["cer"] = a["char_errors"] / a["chars"] if a["chars"] else None
        a["wer"] = a["word_errors"] / a["words"] if a["words"] else None
    report = {
        "dataset": manifest["dataset"],
        "split": manifest["split"],
        "slices": dict(aggregates),
        "samples": rows,
    }
    dump(output / "metrics.json", report)
    with (output / "error_report.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--orientation", choices=["none", "auto"], default="auto")
    p.add_argument("--dpi", type=int, default=200)
    p.add_argument("--max-side", type=int, default=0)
    p.add_argument("--contrast", type=float, default=1)
    p.add_argument("--force-pdf-ocr", action="store_true")
    a = p.parse_args()
    report = benchmark(
        a.manifest,
        a.output,
        ReaderConfig(
            dpi=a.dpi,
            orientation=a.orientation,
            max_side=a.max_side,
            contrast=a.contrast,
            force_pdf_ocr=a.force_pdf_ocr,
        ),
    )
    if any(s["status"] in ("failed", "unexpected_success") for s in report["samples"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
