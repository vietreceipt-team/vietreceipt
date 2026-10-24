"""Import only TV2 validation variants for reproducible Reader diagnostics.

The reference is original SVG text, never OCR output or KIE labels. SVG text
baselines define a provisional row-major order that still needs visual QA. This importer
does not produce independently reviewed transcripts or aligned KIE gold.
"""

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path, PurePosixPath
from uuid import UUID


LAYOUT_SPLITS = {"layout_a": "train", "layout_b": "validation", "layout_c": "test"}
TYPES = {"rendered_png": ".png", "png_image": ".png", "image_only_pdf": ".pdf", "vector_pdf": ".pdf"}
DEGRADATIONS = {"clean", "blur", "noise", "skew"}
SAFE_ID = re.compile(r"[A-Za-z0-9_-]+\Z")
SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
COMMIT = re.compile(r"[0-9a-fA-F]{40}\Z")
REQUIRED = {
    "sample_id", "parent_sample_id", "variant_id", "dataset_family",
    "dataset_snapshot", "document_path", "ground_truth_path", "source_type",
    "synthetic", "split", "layout_id", "mapping_version", "input_type",
    "degradation", "document_sha256", "ground_truth_sha256", "provenance",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_path(root, value):
    """TV2 CSV paths are repository-relative, not CSV-directory-relative."""
    relative = PurePosixPath(value)
    if not value or "\\" in value or ":" in value or relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe repository-relative path: {value}")
    path = (root / Path(*relative.parts)).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Source path escapes source root: {value}")
    return path


def visible_svg_text(path):
    """Read the v0 flat SVG text by baseline y, then anchor x.

    The TV2 generator uses plain text elements with inherited styling. Reject
    hidden/scripted or alternative embedded text so a future generator change
    cannot silently become a trustworthy-looking transcript.
    """
    data = path.read_bytes()
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("SVG declarations/entities are unsupported")
    root = ET.fromstring(data)
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Expected an SVG source document")
    unsupported = {"script", "foreignObject", "use", "switch", "textPath", "tspan"}
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        style = element.get("style", "").replace(" ", "").lower()
        if tag in unsupported or tag == "style":
            raise ValueError(f"Unsupported SVG transcript element: {tag}")
        if "transform" in element.attrib:
            raise ValueError("SVG transforms require manual transcript review")
        if (element.get("display") == "none" or element.get("visibility") in {"hidden", "collapse"}
                or "display:none" in style or "visibility:hidden" in style
                or element.get("opacity") in {"0", "0.0"} or "opacity:0;" in style):
            raise ValueError("Hidden SVG content requires manual transcript review")
    lines = []
    for element in root.iter("{http://www.w3.org/2000/svg}text"):
        try:
            x, y = float(element.attrib["x"]), float(element.attrib["y"])
        except (KeyError, ValueError) as exc:
            raise ValueError("Expected simple numeric x/y coordinates on SVG text") from exc
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Expected finite SVG text coordinates")
        text = " ".join("".join(element.itertext()).split())
        if text:
            lines.append((y, x, text))
    text = "\n".join(line for _, _, line in sorted(lines, key=lambda line: line[:2]))
    if not text:
        raise ValueError("SVG source contains no visible text")
    return text


def read_rows(path, root):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED <= set(reader.fieldnames or []):
            raise ValueError("TV2 rendered manifest is missing required columns")
        rows = list(reader)
    if not rows:
        raise ValueError("TV2 rendered manifest is empty")
    variants, parents = set(), {}
    for row in rows:
        if any(not row.get(key) for key in REQUIRED):
            raise ValueError("TV2 manifest has an empty required value")
        sid, parent, variant = row["sample_id"], row["parent_sample_id"], row["variant_id"]
        if any(not SAFE_ID.fullmatch(value) for value in (sid, parent, variant)):
            raise ValueError("Unsafe TV2 sample/variant ID")
        if sid != parent:
            raise ValueError("Variant sample_id must identify its parent source document")
        if variant in variants:
            raise ValueError(f"Duplicate variant ID: {variant}")
        variants.add(variant)
        if row["layout_id"] not in LAYOUT_SPLITS or LAYOUT_SPLITS[row["layout_id"]] != row["split"]:
            raise ValueError("TV2 layout split leakage or unknown layout")
        if row["synthetic"].lower() != "true" or row["source_type"] != "synthetic_svg":
            raise ValueError("Only the fictional TV2 synthetic SVG source family is supported")
        kind, degradation = row["input_type"], row["degradation"]
        if kind not in TYPES or degradation not in DEGRADATIONS:
            raise ValueError("Unknown TV2 input type or degradation")
        if ((kind in {"rendered_png", "vector_pdf"} and degradation != "clean")
                or (kind == "png_image" and degradation == "clean")):
            raise ValueError("Inconsistent TV2 input type/degradation")
        document = source_path(root, row["document_path"])
        label = source_path(root, row["ground_truth_path"])
        if document.suffix.lower() != TYPES[kind] or label.suffix.lower() != ".json":
            raise ValueError("TV2 input type/path extension mismatch")
        if label.name != parent + ".json" or label.parent.name != "labels":
            raise ValueError("Expected the matching source label under labels/")
        if not all(SHA256.fullmatch(row[key]) for key in ("document_sha256", "ground_truth_sha256")):
            raise ValueError("Invalid TV2 SHA-256 checksum")
        identity = tuple(row[key] for key in ("split", "layout_id", "ground_truth_path",
                         "ground_truth_sha256", "dataset_family", "dataset_snapshot", "mapping_version"))
        if parent in parents and parents[parent] != identity:
            raise ValueError("Parent metadata or split differs across variants")
        parents[parent] = identity
    if len({(r["dataset_family"], r["dataset_snapshot"], r["mapping_version"]) for r in rows}) != 1:
        raise ValueError("Mixed dataset provenance in TV2 manifest")
    return rows


def read_base_manifest(path, root):
    """Check upstream SVG hashes without reading held-out source documents."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_id = {}
    for row in rows:
        parent = row.get("sample_id", "")
        if not SAFE_ID.fullmatch(parent) or parent in by_id:
            raise ValueError("Invalid or duplicate base sample ID")
        if LAYOUT_SPLITS.get(row.get("layout_id")) != row.get("split"):
            raise ValueError("Base source layout split leakage")
        for key in ("document_path", "ground_truth_path"):
            source_path(root, row.get(key, ""))
        if not all(SHA256.fullmatch(row.get(key, "")) for key in ("document_sha256", "ground_truth_sha256")):
            raise ValueError("Invalid base source checksum")
        by_id[parent] = row
    return by_id


def prepare(source_root, manifest_path, source_commit, output, sample_ids=None):
    root, manifest_path, output = Path(source_root).resolve(), Path(manifest_path).resolve(), Path(output).resolve()
    if not COMMIT.fullmatch(source_commit):
        raise ValueError("source_commit must be a full 40-character Git commit SHA")
    if not manifest_path.is_relative_to(root):
        raise ValueError("TV2 manifest must be inside the source root mirror")
    if output.exists():
        raise FileExistsError(output)
    if output == root or root.is_relative_to(output):
        raise ValueError("Output cannot contain the source root")
    rows = read_rows(manifest_path, root)
    validation_ids = {r["parent_sample_id"] for r in rows if r["split"] == "validation"}
    selected_ids = validation_ids if sample_ids is None else set(sample_ids)
    if not selected_ids or not selected_ids <= validation_ids:
        raise ValueError("Only existing validation parent sample IDs may be selected; final test is locked")
    selected = [r for r in rows if r["parent_sample_id"] in selected_ids]
    prepared, sources, base_manifests = [], {}, {}
    for row in selected:
        parent, variant = row["parent_sample_id"], row["variant_id"]
        document = source_path(root, row["document_path"])
        label_path = source_path(root, row["ground_truth_path"])
        if sha256(document) != row["document_sha256"].lower() or sha256(label_path) != row["ground_truth_sha256"].lower():
            raise ValueError(f"TV2 document/label checksum mismatch: {variant}")
        if parent not in sources:
            label = json.loads(label_path.read_text(encoding="utf-8"))
            if (label.get("sample_id") != parent or label.get("template_id") != row["layout_id"]
                    or any(label.get(key) != row[key] for key in ("dataset_family", "dataset_snapshot", "split", "mapping_version"))
                    or label.get("synthetic") is not True):
                raise ValueError(f"Source label identity/provenance mismatch: {parent}")
            try:
                receipt_id = str(UUID(label["receipt_id"]))
            except (KeyError, ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"Invalid source receipt_id: {parent}") from exc
            svg = source_path(root, (PurePosixPath(row["ground_truth_path"]).parent.parent / "documents" / (parent + ".svg")).as_posix())
            base_manifest = label_path.parent.parent / "manifest.csv"
            upstream_verified = False
            if base_manifest.exists():
                if base_manifest not in base_manifests:
                    base_manifests[base_manifest] = read_base_manifest(base_manifest, root)
                base_row = base_manifests[base_manifest].get(parent)
                if (not base_row or any(base_row.get(key) != row[key] for key in (
                        "dataset_family", "dataset_snapshot", "layout_id", "split",
                        "ground_truth_path", "ground_truth_sha256", "mapping_version"))
                        or source_path(root, base_row["document_path"]) != svg):
                    raise ValueError(f"Base/rendered manifest provenance mismatch: {parent}")
                if sha256(svg) != base_row["document_sha256"].lower():
                    raise ValueError(f"Source SVG checksum mismatch: {parent}")
                upstream_verified = True
            sources[parent] = {"svg": svg, "label": label_path, "receipt_id": receipt_id,
                               "reference": visible_svg_text(svg), "svg_sha256": sha256(svg),
                               "upstream_svg_verified": upstream_verified}
        source = sources[parent]
        prepared.append({
            "id": variant, "path": f"inputs/{variant}{document.suffix.lower()}",
            "condition": f"{row['input_type']}_{row['degradation']}",
            "input_sha256": row["document_sha256"].lower(),
            "sample_id": row["sample_id"], "parent_sample_id": parent,
            "variant_id": variant, "layout_id": row["layout_id"],
            "source_split": row["split"], "source_commit": source_commit.lower(),
            "ground_truth_path": f"sources/labels/{parent}.json",
            "ground_truth_sha256": row["ground_truth_sha256"].lower(),
            "source_svg_path": f"sources/documents/{parent}.svg",
            "source_svg_sha256": source["svg_sha256"],
            "receipt_id": source["receipt_id"], "reference": source["reference"],
            "reference_status": "synthetic_source_transcript_unreviewed",
            "reference_provenance": {
                "method": "original_svg_text_sorted_by_numeric_baseline_y_then_x",
                "source_path": f"sources/documents/{parent}.svg",
                "source_sha256": source["svg_sha256"], "human_verified": False,
                "reading_order_assumption": "Flat v0 SVG only: baseline y then anchor x; transforms/tspan unsupported; source/render visual QA is still required",
                "not_derived_from": ["OCR", "KIE labels", "PDF direct text"],
            },
            "source": {**row, "source_commit": source_commit.lower(),
                       "source_svg_sha256": source["svg_sha256"],
                       "copied_label_path": f"sources/labels/{parent}.json"},
        })
    imported = {
        "dataset": rows[0]["dataset_family"], "version": rows[0]["dataset_snapshot"] + "-rendered",
        "split": "validation", "synthetic": True,
        "provenance": {
            "source_commit": source_commit.lower(),
            "source_manifest": manifest_path.relative_to(root).as_posix(),
            "source_manifest_sha256": sha256(manifest_path),
            "base_manifests": [{"path": path.relative_to(root).as_posix(), "sha256": sha256(path)}
                               for path in sorted(base_manifests)],
            "reference_policy": "Synthetic source diagnostics only; not independently reviewed OCR ground truth or aligned KIE gold",
            "test_policy": "Only validation selected; train/test documents and labels are not copied or read",
        },
        "samples": prepared,
    }
    imported["source_provenance"] = imported["provenance"]
    imported["reference_policy"] = imported["provenance"]["reference_policy"]
    output.mkdir(parents=True, exist_ok=False)
    for directory in ("inputs", "sources/documents", "sources/labels"):
        (output / directory).mkdir(parents=True)
    for row, sample in zip(selected, prepared):
        target = output / sample["path"]
        shutil.copyfile(source_path(root, row["document_path"]), target)
        if sha256(target) != row["document_sha256"].lower():
            raise ValueError("Source input changed while copying")
    for parent, source in sources.items():
        for kind, key, suffix in (("documents", "svg", ".svg"), ("labels", "label", ".json")):
            target = output / "sources" / kind / (parent + suffix)
            shutil.copyfile(source[key], target)
            expected = source["svg_sha256"] if key == "svg" else next(r["ground_truth_sha256"].lower() for r in selected if r["parent_sample_id"] == parent)
            if sha256(target) != expected:
                raise ValueError("Source transcription/label changed while copying")
    for name, value in (("manifest.json", imported), ("prepare-report.json", {
        "source_commit": source_commit.lower(), "metadata_rows_checked": len(rows),
        "source_split_counts": dict(Counter(r["split"] for r in rows)),
        "selected_parent_ids": sorted(selected_ids), "selected_samples": len(prepared),
        "selected_split": "validation", "document_and_label_checksums": "pass",
        "reference_human_verified": False, "kie_gold_alignment": "pending_TV2_QA",
        "source_svg_upstream_checksum": "verified_against_base_manifest" if all(s["upstream_svg_verified"] for s in sources.values()) else "not supplied for every source; computed hash preserved",
    })):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "selected-source-manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    return imported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-ids", help="Comma-separated validation parent IDs; default: all validation parents")
    args = parser.parse_args()
    sample_ids = None if args.sample_ids is None else [part.strip() for part in args.sample_ids.split(",")]
    if sample_ids is not None and (not all(sample_ids) or len(set(sample_ids)) != len(sample_ids)):
        parser.error("--sample-ids requires nonempty unique parent IDs")
    result = prepare(args.source_root, args.manifest, args.source_commit, args.output, sample_ids)
    print(f"Prepared {len(result['samples'])} validation variants: {args.output / 'manifest.json'}")
    print("References are unreviewed synthetic SVG source transcriptions; final test remains locked.")


if __name__ == "__main__":
    main()
