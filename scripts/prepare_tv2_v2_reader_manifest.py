"""Import the published TV2 v0.2 development package for paired Reader runs.

Only validation source bytes are opened. Transcripts must match TV2's published
base registry hashes; they are generated source text, not independently reviewed
OCR gold. Existing evidence/aligned candidates are never used as predictions or
references for the new run.
"""

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid5

from scripts.prepare_tv2_reader_manifest import COMMIT, SAFE_ID, SHA256, source_path


LAYOUT_SPLITS = {
    "corporate": "train", "retail": "train", "service": "train",
    "table_heavy": "validation", "long_invoice": "test", "minimal": "test",
}
VARIANTS = {
    "text_pdf": ("text_pdf", "clean", ".pdf"),
    "clean_png": ("image", "clean", ".png"),
    "clean_pdf": ("scanned_pdf", "clean", ".pdf"),
    "blur_png": ("image", "blur", ".png"),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(data):
    return json.loads(data.decode("utf-8-sig"))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checked_member(archive, artifact):
    """Read a declared archive artifact, without ever extracting arbitrary paths."""
    name = artifact.get("path", "")
    relative = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or relative.is_absolute()
            or ".." in relative.parts or not SHA256.fullmatch(artifact.get("sha256", ""))):
        raise ValueError("Unsafe archive artifact path or invalid checksum")
    data = archive.read(name)
    if digest(data) != artifact["sha256"]:
        raise ValueError(f"Archive artifact checksum mismatch: {name}")
    return data


def read_registry(path):
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    if not rows:
        raise ValueError("Empty TV2 base registry")
    registry, seen_hashes = {}, {}
    for row in rows:
        sid = row.get("sample_id", "")
        if not SAFE_ID.fullmatch(sid) or sid in registry:
            raise ValueError("Invalid or duplicate base registry identity")
        if (row.get("base_document_id") != sid or row.get("original_sample_id") != sid
                or row.get("layout_id") != row.get("template_id")
                or LAYOUT_SPLITS.get(row.get("template_id")) != row.get("split")):
            raise ValueError("Base registry identity or template split leakage")
        if (row.get("dataset_family") != "vietreceipt_synthetic"
                or row.get("dataset_version") != "0.2.0"
                or row.get("synthetic", "").lower() != "true"
                or row.get("final_eligible", "").lower() != "false"):
            raise ValueError("Expected TV2 v0.2 fictional development registry")
        for key in ("document_sha256", "ground_truth_sha256", "transcript_sha256"):
            value = row.get(key, "")
            if not SHA256.fullmatch(value):
                raise ValueError("Invalid base registry checksum")
            if value in seen_hashes and seen_hashes[value] != sid:
                raise ValueError("Duplicated content across base documents/splits")
            seen_hashes[value] = sid
        registry[sid] = row
    return registry


def prepare(archive_path, package_path, registry_path, transcript_root, source_commit, output):
    archive_path, package_path, registry_path = map(Path, (archive_path, package_path, registry_path))
    transcript_root, output = Path(transcript_root).resolve(), Path(output).resolve()
    if not COMMIT.fullmatch(source_commit):
        raise ValueError("source_commit must be a full 40-character Git commit SHA")
    if output.exists():
        raise FileExistsError(output)
    if transcript_root == output or transcript_root.is_relative_to(output):
        raise ValueError("Output cannot contain transcript sources")
    package = read_json(package_path.read_bytes())
    archive_hash = digest(archive_path.read_bytes())
    if (archive_hash != package.get("archive_sha256")
            or archive_path.stat().st_size != package.get("bytes")):
        raise ValueError("Published archive checksum/size mismatch")
    registry = read_registry(registry_path)
    validation = {sid: row for sid, row in registry.items() if row["split"] == "validation"}
    if not validation:
        raise ValueError("Registry has no validation parents")
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive member")
        raw_manifest = archive.read("validation-manifest.json")
        if digest(raw_manifest) != package.get("summary", {}).get("validation_manifest_sha256"):
            raise ValueError("Published validation manifest checksum mismatch")
        manifest = read_json(raw_manifest)
        if (manifest.get("split") != "validation" or manifest.get("synthetic") is not True
                or manifest.get("qa_status") != "PENDING_REVIEW"
                or manifest.get("dataset_family") != "vietreceipt_synthetic"
                or manifest.get("dataset_snapshot") != "0.2.0"):
            raise ValueError("Expected pending TV2 v0.2 validation manifest")
        records = manifest["records"]
        expected_ids = {f"{sid}__{variant}" for sid in validation for variant in VARIANTS}
        actual_ids = [r.get("record_id") for r in records]
        if (len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != expected_ids
                or manifest.get("sample_count") != len(records)
                or manifest.get("base_sample_count") != len(validation)):
            raise ValueError("Validation membership differs from complete predefined cohort")
        # Check all declared registry/selection metadata before opening source assets.
        raw_selection = archive.read("selection.csv")
        selection_hash = digest(raw_selection)
        if selection_hash != package.get("summary", {}).get("selection_sha256"):
            raise ValueError("Published selection checksum mismatch")
        selected = list(csv.DictReader(io.StringIO(raw_selection.decode("utf-8-sig"))))
        selected_ids = [r.get("variant_id") for r in selected]
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError("Duplicate selection identity")
        expected_development = {f"{sid}__{variant}" for sid, base in registry.items()
                                if base["split"] in {"train", "validation"} for variant in VARIANTS}
        if set(selected_ids) != expected_development:
            raise ValueError("Selection differs from complete development metadata registry")
        selection_by_id = {r["variant_id"]: r for r in selected}
        selected_validation = set()
        source_hash_parents = {}
        for row in selected:
            base = registry.get(row.get("sample_id"))
            if base is None or row.get("split") not in {"train", "validation"}:
                raise ValueError("Selection contains unknown or locked base")
            for key in ("split", "template_id", "layout_id", "ground_truth_sha256", "transcript_sha256"):
                if row.get(key) != base[key]:
                    raise ValueError("Selection/registry identity or split mismatch")
            parent = base["sample_id"]
            variant = row["variant_id"].removeprefix(parent + "__")
            if variant not in VARIANTS:
                raise ValueError("Selection source variant is not declared")
            kind, augmentation, _ = VARIANTS[variant]
            if (row.get("base_document_id") != parent or row.get("original_sample_id") != parent
                    or row.get("parent_sample_id") != parent
                    or row.get("source_type") != kind or row.get("augmentation_type") != augmentation):
                raise ValueError("Selection source identity/type/augmentation mismatch")
            source_hash = row.get("document_sha256", "")
            if not SHA256.fullmatch(source_hash):
                raise ValueError("Selection source checksum is invalid")
            if source_hash in source_hash_parents and source_hash_parents[source_hash] != parent:
                raise ValueError("Derivative source content duplicated across base documents/splits")
            source_hash_parents[source_hash] = parent
            if row["split"] == "validation":
                selected_validation.add(row["variant_id"])
        if selected_validation != expected_ids:
            raise ValueError("Selection is missing validation source files")
        prepared, blobs, transcript_cache, source_receipts = [], {}, {}, {}
        for record in records:
            sid, parent = record["record_id"], record.get("base_document_id")
            base = validation.get(parent)
            if base is None or record.get("split") != "validation":
                raise ValueError("Non-validation record in validation manifest")
            selected_row = selection_by_id[sid]
            for key in ("document_sha256", "source_type", "augmentation_type", "document_path",
                        "ground_truth_sha256", "transcript_sha256", "transcript_path", "render_spec_path"):
                if record.get(key) != selected_row.get(key):
                    raise ValueError("Validation record differs from exact selected variant")
            variant = sid.removeprefix(parent + "__")
            kind, augmentation, suffix = VARIANTS[variant]
            if (record.get("source_type") != kind or record.get("augmentation_type") != augmentation
                    or any(record.get(k) != base[k] for k in ("template_id", "layout_id", "ground_truth_sha256", "transcript_sha256"))
                    or record.get("parent_sample_id") != parent
                    or record.get("sample_id") != sid or record.get("variant_id") != sid
                    or record.get("original_sample_id") != parent
                    or record.get("source_sample_id") != parent
                    or record.get("qa_status") != "PENDING_REVIEW"):
                raise ValueError("Record source identity/provenance mismatch")
            original = checked_member(archive, record["source"])
            gold_bytes = checked_member(archive, record["source_gold"])
            regions = checked_member(archive, record["source_regions"])
            row_regions = checked_member(archive, record["source_row_regions"])
            if (digest(original) != record.get("document_sha256")
                    or digest(gold_bytes) != base["ground_truth_sha256"]
                    or PurePosixPath(record["source"]["path"]).suffix.lower() != suffix):
                raise ValueError("Source/gold differs from published registry")
            if kind == "text_pdf" and digest(original) != base["document_sha256"]:
                raise ValueError("Text PDF differs from original base document")
            gold = read_json(gold_bytes)
            if (gold.get("sample_id") != parent or gold.get("template_id") != base["template_id"]
                    or gold.get("split") != "validation" or gold.get("dataset_snapshot") != "0.2.0"
                    or gold.get("synthetic") is not True):
                raise ValueError("Source gold metadata mismatch")
            try:
                source_receipt = str(UUID(gold["receipt_id"]))
                receipt = str(UUID(record["receipt_id"]))
            except (KeyError, ValueError, TypeError, AttributeError) as exc:
                raise ValueError("Invalid source/input receipt UUID") from exc
            if (receipt != str(uuid5(UUID(source_receipt), sid))
                    or record.get("source_receipt_id") != source_receipt):
                raise ValueError("Input receipt UUID is not the declared source alias")
            source_receipts[parent] = source_receipt
            if parent not in transcript_cache:
                transcript_path = source_path(transcript_root, base["transcript_path"])
                transcript = transcript_path.read_bytes()
                if digest(transcript) != base["transcript_sha256"]:
                    raise ValueError(f"Published transcript checksum mismatch: {parent}")
                if not transcript.decode("utf-8-sig").strip():
                    raise ValueError("Empty visible source transcript")
                transcript_cache[parent] = transcript
            source_dir = f"sources/{sid}"
            blobs[f"inputs/{sid}{suffix}"] = original
            blobs[f"{source_dir}/source-gold.json"] = gold_bytes
            blobs[f"{source_dir}/source-regions.json"] = regions
            blobs[f"{source_dir}/source-row-regions.json"] = row_regions
            blobs[f"transcripts/{parent}.txt"] = transcript_cache[parent]
            prepared.append({
                "id": sid, "path": f"inputs/{sid}{suffix}",
                "condition": f"{augmentation}_{kind}", "input_sha256": digest(original),
                "receipt_id": receipt, "sample_id": parent, "parent_sample_id": parent,
                "variant_id": sid, "layout_id": base["layout_id"], "source_split": "validation",
                "source_commit": source_commit.lower(), "source_receipt_id": source_receipt,
                "ground_truth_path": f"{source_dir}/source-gold.json",
                "ground_truth_sha256": digest(gold_bytes),
                "source_regions_path": f"{source_dir}/source-regions.json",
                "source_regions_sha256": digest(regions),
                "source_row_regions_path": f"{source_dir}/source-row-regions.json",
                "source_row_regions_sha256": digest(row_regions),
                "transcript_path": f"transcripts/{parent}.txt",
                "transcript_sha256": base["transcript_sha256"],
                "reference": transcript_cache[parent].decode("utf-8-sig"),
                "reference_status": "synthetic_source_transcript_unreviewed",
                "reference_provenance": {
                    "method": "TV2 published visible source transcript; registry hash matched",
                    "source_path": f"transcripts/{parent}.txt",
                    "source_sha256": base["transcript_sha256"], "human_verified": False,
                    "not_derived_from": ["OCR", "KIE predictions", "PDF direct text"],
                },
                "source": record,
            })
    if len(set(source_receipts.values())) != len(source_receipts):
        raise ValueError("Duplicate source receipt identity across base documents")
    provenance = {
        "source_commit": source_commit.lower(), "archive_sha256": archive_hash,
        "package_sha256": digest(package_path.read_bytes()),
        "base_registry_sha256": digest(registry_path.read_bytes()),
        "validation_manifest_sha256": digest(raw_manifest),
        "selection_sha256": selection_hash,
        "reference_policy": "Generated source text diagnostics only; no independent transcript/gold/alignment QA",
        "selection_policy": "Entire predefined validation cohort; no filtering by OCR/evidence success",
        "test_policy": "Only validation assets opened; train/test registry metadata only; final remains locked",
    }
    imported = {
        "dataset": "vietreceipt_synthetic", "version": "0.2.0-tv2-published-development",
        "split": "validation", "synthetic": True, "qa_status": "PENDING_REVIEW",
        "source_provenance": provenance, "provenance": provenance,
        "reference_policy": provenance["reference_policy"], "samples": prepared,
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, data in blobs.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    dump(output / "manifest.json", imported)
    dump(output / "prepare-report.json", {
        "selected_samples": len(prepared), "selected_base_documents": len(validation),
        "layout_counts": dict(Counter(s["layout_id"] for s in prepared)),
        "archive_and_artifact_checksums": "pass", "qa_status": "PENDING_REVIEW",
        "reference_human_verified": False, "kie_gold_alignment": "pending_TV2_TV4_QA",
        **provenance,
    })
    return imported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("archive", "package-json", "registry", "transcript-root", "output"):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    result = prepare(args.archive, args.package_json, args.registry, args.transcript_root,
                     args.source_commit, args.output)
    print(f"Prepared {len(result['samples'])} validation inputs; QA remains PENDING_REVIEW")


if __name__ == "__main__":
    main()
