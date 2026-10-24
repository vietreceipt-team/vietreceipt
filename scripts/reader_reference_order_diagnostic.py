"""Measure sensitivity to generated transcript order, using saved Reader outputs.

The primary published-reference metrics remain untouched. A fixed y/x order of
the independent source render entries is a supplemental, unreviewed diagnostic;
it is not independent ground truth or final OCR/KIE accuracy.
"""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import jiwer

from scripts.prepare_tv2_reader_manifest import SAFE_ID, source_path


MODES = ("ocr_all", "route_aware")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def normalize(text):
    return " ".join(text.split())


def measures(reference, predicted):
    ref, hyp = normalize(reference), normalize(predicted)
    characters = jiwer.process_characters(ref, hyp)
    words = jiwer.process_words(ref, hyp)
    return {
        "cer": characters.cer, "wer": words.wer,
        "char_errors": characters.substitutions + characters.insertions + characters.deletions,
        "chars": len(ref), "word_errors": words.substitutions + words.insertions + words.deletions,
        "words": len(ref.split()),
    }


def ordered_reference(spec, reference, layout):
    if spec.get("layout") != layout:
        raise ValueError("Render specification layout does not match declared source")
    entries = spec.get("entries")
    if not entries:
        raise ValueError("Render specification contains no visible entries")
    for entry in entries:
        if (not isinstance(entry.get("text"), str) or not entry["text"].strip()
                or "\n" in entry["text"] or "\r" in entry["text"]):
            raise ValueError("Render entry must be a complete visible source line")
        if any(isinstance(entry.get(axis), bool) or not isinstance(entry.get(axis), (int, float))
               or not math.isfinite(entry[axis]) for axis in ("x", "y")):
            raise ValueError("Render entry requires finite numeric source coordinates")
    if Counter(e["text"] for e in entries) != Counter(reference.splitlines()):
        raise ValueError("Visible-entry multiset differs from published source transcript")
    # Stable ties preserve the generator entry order; no prediction is consulted.
    return "\n".join(e["text"] for e in sorted(entries, key=lambda e: (e["y"], e["x"]))) + "\n"


def diagnose(run_dir, manifest_path, render_spec_root, output):
    run_dir, manifest_path, render_spec_root, output = map(
        lambda p: Path(p).resolve(), (run_dir, manifest_path, render_spec_root, output))
    if output.exists():
        raise FileExistsError(output)
    if output == run_dir or run_dir.is_relative_to(output):
        raise ValueError("Diagnostic output cannot contain the original run")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    if manifest.get("split") not in {"development", "dev", "validation"}:
        raise ValueError("Only development/validation sources may be diagnosed")
    samples = manifest["samples"]
    ids = [sample["id"] for sample in samples]
    if not ids or len(ids) != len(set(ids)) or any(not SAFE_ID.fullmatch(sid) for sid in ids):
        raise ValueError("Expected unique safe sample identities")
    handoff_path = run_dir / "handoff.json"
    handoff_bytes = handoff_path.read_bytes()
    handoff = json.loads(handoff_bytes.decode("utf-8-sig"))
    if handoff.get("manifest_sha256") != sha(manifest_bytes):
        raise ValueError("Saved run does not match the supplied primary manifest")
    evidence_index = {}
    for record in handoff["samples"]:
        key = (record["mode"], record["id"])
        if key in evidence_index or key[0] not in MODES or key[1] not in set(ids):
            raise ValueError("Unexpected or duplicate handoff identity")
        evidence_index[key] = record
    reconstruction_path = render_spec_root / "reconstruction.json"
    reconstruction_bytes = reconstruction_path.read_bytes()
    reconstruction = json.loads(reconstruction_bytes.decode("utf-8-sig"))
    source_commit = manifest.get("source_provenance", {}).get("source_commit")
    if not source_commit or reconstruction.get("source_commit") != source_commit:
        raise ValueError("Render specification reconstruction revision differs from source dataset")
    references, input_hashes, metric_hashes = {}, {}, {}
    for sample in samples:
        parent = sample.get("parent_sample_id", "")
        if not SAFE_ID.fullmatch(parent) or sample.get("source_split") != "validation":
            raise ValueError("Expected declared validation parent identity")
        transcript_path = source_path(manifest_path.parent, sample["transcript_path"])
        transcript = transcript_path.read_bytes()
        if sha(transcript) != sample["transcript_sha256"] or transcript.decode("utf-8-sig") != sample["reference"]:
            raise ValueError("Primary source transcript changed")
        spec_path = source_path(render_spec_root, f"render_specs/{parent}.json")
        spec_bytes = spec_path.read_bytes()
        alternate = ordered_reference(json.loads(spec_bytes.decode("utf-8-sig")), sample["reference"], sample["layout_id"])
        reference_record = {
            "parent_sample_id": parent, "layout_id": sample["layout_id"],
            "published_transcript_sha256": sample["transcript_sha256"],
            "render_spec_path": spec_path.relative_to(render_spec_root).as_posix(),
            "render_spec_sha256": sha(spec_bytes), "source_commit": source_commit,
            "row_major_reference_sha256": sha(alternate.encode("utf-8")),
            "published_reference": sample["reference"], "row_major_reference": alternate,
            "reference_order_changed": normalize(alternate) != normalize(sample["reference"]),
            "method": "stable source render entries sorted by numeric y then x; no prediction input",
            "human_verified": False,
        }
        if parent in references and references[parent] != reference_record:
            raise ValueError("Variants disagree about original source reference/specification")
        references[parent] = reference_record
        input_hashes[str(transcript_path)] = sha(transcript)
        input_hashes[str(spec_path)] = sha(spec_bytes)
    rows = []
    counters = defaultdict(lambda: {"samples": 0, "failures": 0, "published_reference": Counter(), "row_major_reference": Counter()})
    for mode in MODES:
        metrics_path = run_dir / mode / "metrics.json"
        metrics_bytes = metrics_path.read_bytes()
        metric_hashes[mode] = sha(metrics_bytes)
        original = json.loads(metrics_bytes.decode("utf-8-sig"))
        metric_ids = [r["id"] for r in original["samples"]]
        if len(metric_ids) != len(set(metric_ids)) or set(metric_ids) != set(ids):
            raise ValueError("Saved metrics must preserve the complete primary denominator")
        by_id = {r["id"]: r for r in original["samples"]}
        for sample in samples:
            sid, original_row = sample["id"], by_id[sample["id"]]
            reference = references[sample["parent_sample_id"]]
            status = original_row["status"]
            if original_row.get("input_sha256") != sample["input_sha256"]:
                raise ValueError("Saved metrics refer to different original input bytes")
            predicted, evidence_hash = "", None
            if status == "ok":
                record = evidence_index.get((mode, sid))
                if record is None or record.get("input_sha256") != sample["input_sha256"]:
                    raise ValueError("Successful output has no matching immutable handoff")
                evidence_path = source_path(run_dir, record["evidence_path"])
                evidence_bytes = evidence_path.read_bytes()
                evidence_hash = sha(evidence_bytes)
                if evidence_hash != record["evidence_sha256"]:
                    raise ValueError("Saved Reader evidence checksum changed")
                document = json.loads(evidence_bytes.decode("utf-8-sig"))
                if (document.get("receipt_id") != sample["receipt_id"]
                        or document.get("receipt_id") != record["receipt_id"]
                        or document.get("ocr_run_id") != record["ocr_run_id"]):
                    raise ValueError("Saved evidence identity differs from declared handoff")
                predicted = " ".join(b["text"] for p in document["pages"] for b in p["evidence"]["blocks"])
                input_hashes[str(evidence_path)] = evidence_hash
            elif status not in {"failed", "expected_failure"}:
                raise ValueError("Unsupported saved Reader status")
            primary = measures(reference["published_reference"], predicted)
            alternate = measures(reference["row_major_reference"], predicted)
            if any(original_row.get(key) is None or not math.isclose(original_row[key], primary[key], rel_tol=1e-12, abs_tol=1e-12)
                   for key in ("cer", "wer")):
                raise ValueError("Recomputed primary metrics differ from immutable saved metrics")
            row = {
                "id": sid, "mode": mode, "condition": sample.get("condition", "unspecified"),
                "parent_sample_id": sample["parent_sample_id"], "original_status": status,
                "input_sha256": sample["input_sha256"], "evidence_sha256": evidence_hash,
                "published_reference_sha256": sample["transcript_sha256"],
                "render_spec_sha256": reference["render_spec_sha256"],
                "row_major_reference_sha256": reference["row_major_reference_sha256"],
                "reference_order_changed": reference["reference_order_changed"],
                "original_cer": original_row["cer"], "original_wer": original_row["wer"],
                "row_major_cer": alternate["cer"], "row_major_wer": alternate["wer"],
                "cer_delta_row_major_minus_published": alternate["cer"] - primary["cer"],
                "wer_delta_row_major_minus_published": alternate["wer"] - primary["wer"],
                "interpretation": "reference-order sensitivity; unreviewed development diagnostic",
            }
            rows.append(row)
            for condition in {"all", row["condition"]}:
                counter = counters[(mode, condition)]
                counter["samples"] += 1
                counter["failures"] += status != "ok"
                for name, values in (("published_reference", primary), ("row_major_reference", alternate)):
                    counter[name].update({k: values[k] for k in ("char_errors", "chars", "word_errors", "words")})
    slices = {mode: {} for mode in MODES}
    for (mode, condition), counter in counters.items():
        for key in ("published_reference", "row_major_reference"):
            counter[key] = dict(counter[key])
            counter[key]["cer"] = counter[key]["char_errors"] / counter[key]["chars"]
            counter[key]["wer"] = counter[key]["word_errors"] / counter[key]["words"]
        slices[mode][condition] = counter
    # Recheck all observed sources immediately before writing a separate output.
    immutable = {
        str(manifest_path): sha(manifest_bytes), str(handoff_path): sha(handoff_bytes),
        str(reconstruction_path): sha(reconstruction_bytes), **input_hashes,
        **{str(run_dir / mode / "metrics.json"): value for mode, value in metric_hashes.items()},
    }
    if any(sha(Path(path).read_bytes()) != expected for path, expected in immutable.items()):
        raise ValueError("Primary input/output changed during supplemental diagnostic")
    report = {
        "interpretation": "Reference-order sensitivity only; generated unreviewed source entries, not final OCR/KIE accuracy",
        "primary_metrics_unchanged": True, "human_verified": False,
        "primary_manifest_sha256": sha(manifest_bytes), "handoff_sha256": sha(handoff_bytes),
        "original_metrics_sha256": metric_hashes,
        "reconstruction_sha256": sha(reconstruction_bytes), "source_commit": source_commit,
        "failure_policy": "Every primary sample retained; failed reads use empty predictions",
        "reference_method": "Stable numeric source y then x; ordering uses source entries only",
        "analysis_status": "post_hoc_exploratory_reference_order_control; not a preregistered accuracy endpoint",
        "references": list(references.values()), "slices": slices, "samples": rows,
    }
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "reference-order.json", report)
    with (output / "reference-order.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("run-dir", "manifest", "render-spec-root", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    result = diagnose(args.run_dir, args.manifest, args.render_spec_root, args.output)
    print(f"Wrote {len(result['samples'])} supplemental order diagnostics; primary metrics unchanged")


if __name__ == "__main__":
    main()
