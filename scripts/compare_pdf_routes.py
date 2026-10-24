"""Paired OCR-all vs route-aware diagnostics on identical manifest bytes (TV3 #48)."""

import argparse
import csv
import hashlib
import json
import os
import shutil
import statistics
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
                "metadata_sha256": hashlib.sha256(path.with_suffix(".metadata.json").read_bytes()).hexdigest(),
                "alignment_status": "awaiting_TV2_source_gold_and_QA",
                "source_provenance": {
                    key: sample[key] for key in (
                        "sample_id", "parent_sample_id", "variant_id", "layout_id", "source_split",
                        "source_commit", "ground_truth_path", "ground_truth_sha256",
                        "source_svg_path", "source_svg_sha256", "reference_status",
                        "record_id", "base_document_id", "source_gold_path", "source_gold_sha256",
                        "source_regions_path", "source_regions_sha256", "transcript_path", "transcript_sha256",
                        "reference_provenance", "qa_status",
                    ) if key in sample
                },
            })
            if sample.get("reference"):
                examples.extend(dict(e, id=sid, mode=mode, evidence_path=path.relative_to(output).as_posix())
                                for e in error_examples(sample["reference"], document))
        row["cer_delta_route_minus_ocr"] = b["cer"] - a["cer"] if a["cer"] is not None and b["cer"] is not None else None
        pairs.append(row)
    # PDF-only summaries retain scan/fallback routes and failures, rather than
    # pooling PNGs into a claimed routing benefit. Timings are observed serial
    # samples, including cold starts; they are not a latency distribution study.
    pdf_ids = {s["id"] for s in manifest["samples"] if Path(s["path"]).suffix.lower() == ".pdf"}
    pdf_samples = [s for s in manifest["samples"] if s["id"] in pdf_ids]
    pdf_summary = {"sample_count": len(pdf_ids), "independent_base_documents": len({
        s.get("base_document_id", s.get("parent_sample_id", s["id"])) for s in pdf_samples
    }), "input_hash_paired": True, "modes": {}}
    for mode, report in reports.items():
        selected = [r for r in report["samples"] if r["id"] in pdf_ids]
        referenced = [r for r in selected if r["reference_chars"] is not None]
        chars = sum(r["reference_chars"] for r in referenced)
        # Word counts are from the same frozen reference, including failed reads.
        references = {s["id"]: " ".join((s.get("reference") or "").split()) for s in pdf_samples}
        words = sum(len(references[r["id"]].split()) for r in referenced)
        durations = [r["wall_duration_ms"] for r in selected]
        mode_pages = [p for p in pages if p["mode"] == mode and p["id"] in pdf_ids]
        pdf_summary["modes"][mode] = {
            "attempted": len(selected), "failed": sum(r["status"] == "failed" for r in selected),
            "referenced": len(referenced), "reference_chars": chars, "reference_words": words,
            "cer": sum(r["cer"] * r["reference_chars"] for r in referenced) / chars if chars else None,
            "wer": sum(r["wer"] * len(references[r["id"]].split()) for r in referenced) / words if words else None,
            "wall_ms_total": sum(durations), "wall_ms_mean": statistics.mean(durations) if durations else None,
            "wall_ms_median": statistics.median(durations) if durations else None,
            "cold_start_candidates": [r["id"] for r in selected if r["cold_start_candidate"]],
            "fallback_pages": sum(p["fallback"] for p in mode_pages),
            "pdf_text_pages": sum(p["route"] == "PDF_TEXT" for p in mode_pages),
            "ocr_pages": sum(p["route"] != "PDF_TEXT" for p in mode_pages),
            "failures": [{"id": r["id"], "error": r["error"]} for r in selected if r["status"] != "ok"],
        }
    dump(output / "comparison.json", {
        "dataset": manifest["dataset"], "version": manifest["version"], "split": manifest["split"],
        "interpretation": "development diagnostics; not final accuracy or KIE scores",
        "source_provenance": manifest.get("source_provenance"),
        "reference_policy": manifest.get("reference_policy"),
        "paired_pdf_summary": pdf_summary,
        "slices": {mode: report["slices"] for mode, report in reports.items()}, "samples": pairs,
    })
    write_csv(output / "comparison.csv", pairs)
    write_csv(output / "pages.csv", pages)
    dump(output / "handoff.json", {
        "dataset": manifest["dataset"], "version": manifest["version"], "split": manifest["split"],
        "source_provenance": manifest.get("source_provenance"),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest() if manifest_path else None,
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
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    manifest = load_manifest(manifest_path)
    if manifest["split"].lower() not in {"development", "dev", "validation"}:
        raise ValueError("Use a development/validation manifest; final test is locked")
    if not any(Path(s["path"]).suffix.lower() == ".pdf" for s in manifest["samples"]):
        raise ValueError("Paired PDF comparison requires PDF samples")
    transcripts = {}
    for sample in manifest["samples"]:
        if not any(key in sample for key in ("transcript_path", "transcript_sha256")):
            continue  # Legacy inline-only references remain explicitly in the manifest.
        if not all(sample.get(key) for key in ("transcript_path", "transcript_sha256", "reference")):
            raise ValueError("Declared transcript reference is incomplete")
        path = (manifest_path.parent / sample["transcript_path"]).resolve()
        if not path.is_relative_to(manifest_path.parent.resolve()):
            raise ValueError("Transcript path escapes manifest directory")
        data = path.read_bytes()
        if (hashlib.sha256(data).hexdigest() != sample["transcript_sha256"]
                or data.decode("utf-8-sig") != sample["reference"]):
            raise ValueError("Published transcript hash/inline reference mismatch")
        transcripts[path] = sample["transcript_sha256"]

    def check_references():
        if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != manifest_hash:
            raise ValueError("Manifest/reference changed during paired comparison")
        if any(hashlib.sha256(path.read_bytes()).hexdigest() != expected
               for path, expected in transcripts.items()):
            raise ValueError("Transcript changed during paired comparison")

    check_references()
    output.mkdir(parents=True, exist_ok=False)
    reports = {}
    # Freeze and hash the same input files; verify again after both passes.
    frozen = {s["id"]: hashlib.sha256((manifest_path.parent / s["path"]).read_bytes()).hexdigest()
              for s in manifest["samples"] if (manifest_path.parent / s["path"]).is_file()}
    for mode, forced in (("ocr_all", True), ("route_aware", False)):
        check_references()
        mode_config = replace(config, force_pdf_ocr=forced)
        reports[mode] = benchmark(manifest_path, output / mode, mode_config,
                                  reader_factory=reader_factory)
        check_references()
        saved_config = read_json(output / mode / "config.json")
        if (saved_config["manifest_sha256"] != manifest_hash
                or saved_config["config"] != mode_config.__dict__
                or read_json(output / mode / "manifest.json") != manifest):
            raise ValueError("Mode manifest/config snapshot differs from frozen comparison")
        for row in reports[mode]["samples"]:
            if row["input_sha256"] != frozen.get(row["id"]):
                raise ValueError("Input bytes changed during comparison")
    check_references()
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
