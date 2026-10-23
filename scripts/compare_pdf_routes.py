"""Paired OCR-all vs route-aware diagnostics on identical manifest bytes (TV3 #48)."""

import argparse
import csv
import hashlib
import json
import os
import shutil
import unicodedata
from dataclasses import replace
from difflib import SequenceMatcher
from pathlib import Path

from ai.document_reader import ReaderConfig
from ai.document_reader.contract import validate_document
from scripts.benchmark_document_reader import benchmark, dump, load_manifest


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def unaccent(text):
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if not unicodedata.combining(c)).replace("đ", "d").replace("Đ", "D")


def error_examples(reference, document, *, limit=5):
    """Text differences are candidates; never infer order/geometry from CER alone."""
    reference = " ".join(reference.split())
    tokens, spans, offset = [], [], 0
    for page in document["pages"]:
        for block in page["evidence"]["blocks"]:
            text = " ".join(block["text"].split())
            if not text:
                continue
            if tokens:
                offset += 1
            spans.append((offset, offset + len(text), page["page_index"], block))
            offset += len(text)
            tokens.append(text)
    hypothesis = " ".join(tokens)
    examples = []
    for tag, a, b, c, d in SequenceMatcher(None, reference, hypothesis, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        expected, actual = reference[a:b], hypothesis[c:d]
        category = {"delete": "omission", "insert": "insertion", "replace": "substitution"}[tag]
        if expected != actual and unaccent(expected) == unaccent(actual):
            category = "diacritics"
        linked = [
            {"page_index": page, "block_id": block["block_id"],
             "reading_order": block["reading_order"], "text": block["text"],
             "polygon": block["polygon"]}
            for start, end, page, block in spans
            if start < max(c + 1, d) and end > c
        ]
        examples.append({
            "category": category, "reference_span": [a, b], "prediction_span": [c, d],
            "expected": expected, "actual": actual,
            "reference_context": reference[max(0, a - 35):b + 35],
            "prediction_context": hypothesis[max(0, c - 35):d + 35],
            "evidence": linked, "review_status": "text_diff_candidate",
        })
        if len(examples) >= limit:
            break
    return examples


def summarize(output, manifest, reports, *, manifest_path=None):
    pairs, pages, handoff, examples = [], [], [], []
    by_mode = {mode: {r["id"]: r for r in report["samples"]}
               for mode, report in reports.items()}
    for sample in manifest["samples"]:
        sid = sample["id"]
        a, b = by_mode["ocr_all"][sid], by_mode["route_aware"][sid]
        if a["input_sha256"] != b["input_sha256"]:
            raise ValueError(f"Paired input changed: {sid}")
        row = {"id": sid, "condition": sample.get("condition", "unspecified"),
               "input_sha256": a["input_sha256"]}
        for mode, result in (("ocr_all", a), ("route_aware", b)):
            for key in ("status", "error", "cer", "wer", "char_deletions",
                        "char_substitutions", "char_insertions", "duration_ms",
                        "wall_duration_ms", "cold_start_candidate"):
                row[f"{mode}_{key}"] = result[key]
            path = output / mode / "predictions" / f"{sid}.json"
            if not path.exists():
                continue
            document = read_json(path)
            validate_document(document)
            metadata = read_json(path.with_suffix(".metadata.json"))
            for page, meta in zip(document["pages"], metadata["pages"]):
                stages = meta.get("stage_latency_ms", {})
                pages.append({
                    "id": sid, "mode": mode, "page_index": page["page_index"],
                    "route": meta["source"], "routing_reason": meta["routing_reason"],
                    "fallback": meta["fallback"],
                    "orientation_clockwise": meta.get("orientation_clockwise", 0),
                    "pdf_text_ms": stages.get("pdf_text", 0),
                    "render_ms": stages.get("render", 0),
                    "preprocess_orientation_ms": stages.get("preprocess_orientation", 0),
                    "ocr_ms": stages.get("ocr", 0), "geometry_order_ms": stages.get("geometry_order", 0),
                    "confidence": None if meta["source"] == "PDF_TEXT" else page["evidence"]["average_confidence"],
                    "confidence_semantics": meta["confidence_semantics"],
                })
            handoff.append({
                "id": sid, "mode": mode, "receipt_id": document["receipt_id"],
                "ocr_run_id": document["ocr_run_id"], "input_sha256": result["input_sha256"],
                "source_path": sample["path"],
                "evidence_path": path.relative_to(output).as_posix(),
                "evidence_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "metadata_path": path.with_suffix(".metadata.json").relative_to(output).as_posix(),
                "alignment_status": "awaiting_TV2_source_gold_and_QA",
                "source_provenance": {
                    key: sample[key] for key in (
                        "sample_id", "parent_sample_id", "variant_id", "layout_id", "source_split",
                        "source_commit", "ground_truth_path", "ground_truth_sha256",
                        "source_svg_path", "source_svg_sha256", "reference_status",
                    ) if key in sample
                },
            })
            if sample.get("reference"):
                examples.extend(dict(e, id=sid, mode=mode, evidence_path=path.relative_to(output).as_posix())
                                for e in error_examples(sample["reference"], document))
        row["cer_delta_route_minus_ocr"] = b["cer"] - a["cer"] if a["cer"] is not None and b["cer"] is not None else None
        pairs.append(row)
    dump(output / "comparison.json", {
        "dataset": manifest["dataset"], "version": manifest["version"], "split": manifest["split"],
        "interpretation": "development diagnostics; not final accuracy or KIE scores",
        "source_provenance": manifest.get("source_provenance"),
        "reference_policy": manifest.get("reference_policy"),
        "slices": {mode: report["slices"] for mode, report in reports.items()}, "samples": pairs,
    })
    write_csv(output / "comparison.csv", pairs)
    write_csv(output / "pages.csv", pages)
    dump(output / "handoff.json", {
        "dataset": manifest["dataset"], "version": manifest["version"], "split": manifest["split"],
        "source_provenance": manifest.get("source_provenance"),
        "input_manifest_path": os.path.relpath(manifest_path.resolve(), output.resolve()).replace("\\", "/")
        if manifest_path else None,
        "source_paths_relative_to": "input_manifest_path parent directory",
        "samples": handoff,
    })
    dump(output / "error_examples.json", {
        "policy": "Character diffs only; order/geometry/PDF rendering require source-overlay review. Omission can have no predicted block.",
        "examples": examples,
    })
    dump(output / "runtime.json", {
        "native": {"status": "see per-sample results", "configuration": "ocr_all/config.json"},
        "docker": {"cli_available": shutil.which("docker") is not None,
                   "smoke_status": "not_tested", "linux_arm64_scan_support": "not_verified"},
    })
    return pairs


def compare(manifest_path, output, config, *, reader_factory=None):
    manifest = load_manifest(manifest_path)
    if manifest["split"].lower() not in {"development", "dev", "validation"}:
        raise ValueError("Use a development/validation manifest; final test is locked")
    if not any(Path(s["path"]).suffix.lower() == ".pdf" for s in manifest["samples"]):
        raise ValueError("Paired PDF comparison requires PDF samples")
    output.mkdir(parents=True, exist_ok=False)
    reports = {}
    # Freeze and hash the same input files; verify again after both passes.
    frozen = {s["id"]: hashlib.sha256((manifest_path.parent / s["path"]).read_bytes()).hexdigest()
              for s in manifest["samples"] if (manifest_path.parent / s["path"]).is_file()}
    for mode, forced in (("ocr_all", True), ("route_aware", False)):
        reports[mode] = benchmark(manifest_path, output / mode, replace(config, force_pdf_ocr=forced),
                                  reader_factory=reader_factory)
        for row in reports[mode]["samples"]:
            if row["input_sha256"] != frozen.get(row["id"]):
                raise ValueError("Input bytes changed during comparison")
    return summarize(output, manifest, reports, manifest_path=manifest_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--orientation", choices=["auto", "none"], default="auto")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--max-side", type=int, default=0)
    parser.add_argument("--contrast", type=float, default=1)
    args = parser.parse_args()
    rows = compare(args.manifest, args.output, ReaderConfig(
        orientation=args.orientation, dpi=args.dpi, max_side=args.max_side, contrast=args.contrast))
    if any(row[f"{mode}_status"] in {"failed", "unexpected_success"}
           for row in rows for mode in ("ocr_all", "route_aware")):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
