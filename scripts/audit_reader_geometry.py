"""Audit saved Reader source frames and export TV2/TV4 linkage, without inference.

This verifies identities, hashes and geometric *contracts*. It does not establish
that a polygon encloses the intended text or that source gold has human approval.
"""

import argparse
import csv
import hashlib
import json
import math
from contextlib import closing
from pathlib import Path

from PIL import Image, ImageOps

from ai.document_reader.contract import validate_document


IMAGE_FRAME = "normalized_exif_display_top_left"
PDF_FRAME = "normalized_crop_unrotated_top_left"
RESTORE = {
    0: "(x, y)",
    90: "(y, 1-x)",
    180: "(1-x, 1-y)",
    270: "(1-y, x)",
}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes its root")
    return path


def source_frames(path, dpi):
    """Inspect source byte geometry in exactly the Reader's canonical frame."""
    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium

        frames = []
        with pdfium.PdfDocument(path) as pdf:
            for index in range(len(pdf)):
                with closing(pdf[index]) as page:
                    rotation = page.get_rotation()
                    page.set_rotation(0)
                    width, height = page.get_size()
                    crop = list(page.get_bbox())
                    frames.append({
                        "page_index": index, "coordinate_system": PDF_FRAME,
                        "width_px": math.ceil(width * dpi / 72),
                        "height_px": math.ceil(height * dpi / 72),
                        "page_width_pt": width, "page_height_pt": height,
                        "effective_crop_bbox_pdf_points": crop,
                        "intrinsic_rotation": rotation, "canonical_rotation": 0,
                        "dpi": dpi, "raw_exif_orientation": None,
                        "raw_image_width_px": None, "raw_image_height_px": None,
                    })
        return frames
    with Image.open(path) as image:
        raw_width, raw_height = image.size
        orientation = image.getexif().get(274, 1)
        width, height = ImageOps.exif_transpose(image).size
    return [{
        "page_index": 0, "coordinate_system": IMAGE_FRAME,
        "width_px": width, "height_px": height,
        "page_width_pt": None, "page_height_pt": None,
        "effective_crop_bbox_pdf_points": None,
        "intrinsic_rotation": None, "canonical_rotation": None, "dpi": None,
        "raw_exif_orientation": orientation,
        "raw_image_width_px": raw_width, "raw_image_height_px": raw_height,
    }]


def _csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def audit(run_dir, manifest_path, output):
    run_dir, manifest_path, output = map(Path, (run_dir, manifest_path, output))
    run_dir, manifest_path = run_dir.resolve(), manifest_path.resolve()
    if output.exists():
        raise FileExistsError(output)
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    if manifest.get("split", "").lower() not in {"validation", "development", "dev"}:
        raise ValueError("Only development/validation geometry may be audited")
    samples = manifest["samples"]
    by_id = {s["id"]: s for s in samples}
    if not samples or len(by_id) != len(samples):
        raise ValueError("Expected unique nonempty manifest samples")
    handoff_path = run_dir / "handoff.json"
    handoff = _read(handoff_path)
    declared_manifest_sha256 = handoff.get("manifest_sha256")
    if declared_manifest_sha256 is not None and declared_manifest_sha256 != manifest_sha256:
        raise ValueError("Handoff manifest hash differs from supplied manifest")
    if any(handoff.get(k) != manifest.get(k) for k in ("dataset", "version", "split")):
        raise ValueError("Handoff dataset identity differs from manifest")
    comparison = _read(run_dir / "comparison.json")
    rows = comparison["samples"]
    comparison_by_id = {r["id"]: r for r in rows}
    if len(comparison_by_id) != len(rows) or set(comparison_by_id) != set(by_id):
        raise ValueError("Comparison cohort differs from manifest")
    pages, blocks, identities = [], [], set()
    run_ids = set()
    frames_cache = {}
    for item in handoff["samples"]:
        sid, mode = item["id"], item["mode"]
        if sid not in by_id or mode not in {"ocr_all", "route_aware"}:
            raise ValueError("Unknown handoff sample or mode")
        key = (sid, mode)
        if key in identities:
            raise ValueError("Duplicate handoff sample/mode")
        identities.add(key)
        sample = by_id[sid]
        source = _inside(manifest_path.parent, sample["path"])
        source_hash = _sha(source)
        if item["source_path"] != sample["path"] or source_hash != item["input_sha256"]:
            raise ValueError("Handoff source path/hash mismatch")
        if sample.get("input_sha256", source_hash) != source_hash:
            raise ValueError("Manifest source hash mismatch")
        if comparison_by_id[sid]["input_sha256"] != source_hash:
            raise ValueError("Comparison source hash mismatch")
        path = _inside(run_dir, item["evidence_path"])
        if _sha(path) != item["evidence_sha256"]:
            raise ValueError("Evidence hash mismatch")
        metadata_path = _inside(run_dir, item["metadata_path"])
        metadata_hash = _sha(metadata_path)
        if item.get("metadata_sha256", metadata_hash) != metadata_hash:
            raise ValueError("Metadata hash mismatch")
        document, metadata = _read(path), _read(metadata_path)
        validate_document(document)
        if any(document[k] != item[k] for k in ("receipt_id", "ocr_run_id")):
            raise ValueError("Evidence run identity differs from handoff")
        if sample.get("receipt_id", document["receipt_id"]) != document["receipt_id"]:
            raise ValueError("Source receipt identity differs from evidence")
        if document["ocr_run_id"] in run_ids:
            raise ValueError("OCR run ID was reused across samples or modes")
        run_ids.add(document["ocr_run_id"])
        if metadata.get("input_sha256") != source_hash:
            raise ValueError("Metadata source hash mismatch")
        config = metadata["config"]
        dpi = config["dpi"]
        if config.get("force_pdf_ocr") is not (mode == "ocr_all"):
            raise ValueError("Metadata forced-OCR mode differs from comparison")
        cache_key = (str(source), dpi)
        if cache_key not in frames_cache:
            frames_cache[cache_key] = source_frames(source, dpi)
        frames = frames_cache[cache_key]
        if len(document["pages"]) != len(metadata["pages"]) or len(frames) != len(document["pages"]):
            raise ValueError("Source/evidence/metadata page counts differ")
        for index, (page, meta, frame) in enumerate(zip(document["pages"], metadata["pages"], frames)):
            if meta.get("page_index", index) != index:
                raise ValueError("Metadata page index differs from evidence")
            if meta.get("coordinate_system") != frame["coordinate_system"]:
                raise ValueError("Metadata coordinate frame differs from source")
            evidence = page["evidence"]
            size = evidence["image"]
            if size != {k: frame[k] for k in ("width_px", "height_px")}:
                raise ValueError("Evidence dimensions differ from canonical source frame")
            angle = meta.get("orientation_clockwise", 0)
            if angle not in RESTORE:
                raise ValueError("Unsupported OCR rotation")
            if frame["coordinate_system"] == PDF_FRAME:
                if (meta.get("canonical_rotation") != 0
                        or meta.get("intrinsic_rotation") != frame["intrinsic_rotation"]
                        or meta.get("dpi") != dpi):
                    raise ValueError("PDF rotation/DPI metadata differs from source")
                if meta.get("source") not in {"PDF_OCR", "PDF_TEXT"}:
                    raise ValueError("PDF route metadata differs from source type")
            elif meta.get("source") != "IMAGE_OCR":
                raise ValueError("Image route metadata differs from source type")
            if mode == "ocr_all" and meta.get("source") == "PDF_TEXT":
                raise ValueError("OCR-all unexpectedly used PDF text")
            if meta.get("source") == "PDF_TEXT" and angle:
                raise ValueError("Direct PDF text must use unrotated source coordinates")
            # Reader thumbnail preserves aspect ratio; polygons are normalized
            # before inverse rotation, so no resize factor is applied to them.
            resize = config.get("max_side", 0)
            work_width, work_height = size["width_px"], size["height_px"]
            if meta["source"] != "PDF_TEXT" and resize and max(work_width, work_height) > resize:
                with Image.new("L", (work_width, work_height)) as thumbnail:
                    thumbnail.thumbnail((resize, resize))
                    work_width, work_height = thumbnail.size
            if angle in {90, 270}:
                work_width, work_height = work_height, work_width
            common = {
                "id": sid, "mode": mode, "receipt_id": document["receipt_id"],
                "ocr_run_id": document["ocr_run_id"], "page_index": index,
                "input_sha256": source_hash, "evidence_path": item["evidence_path"],
                "evidence_sha256": item["evidence_sha256"],
                "metadata_path": item["metadata_path"], "metadata_sha256": metadata_hash,
                **frame,
            }
            pages.append({
                **common, "route": meta["source"], "fallback": meta["fallback"],
                "block_count": len(evidence["blocks"]),
                "orientation_clockwise": angle,
                "inverse_ocr_rotation_normalized_xy": RESTORE[angle],
                "ocr_width_px_derived": work_width, "ocr_height_px_derived": work_height,
                "resize_policy": "aspect-preserving thumbnail; normalized coordinates remain in source frame",
                "contract_status": "pass", "visual_alignment": "pending_human_source_review",
            })
            for block in evidence["blocks"]:
                points = block["polygon"]
                blocks.append({
                    **common, "block_id": block["block_id"],
                    "reading_order": block["reading_order"], "text": block["text"],
                    "polygon_normalized_json": json.dumps(points, separators=(",", ":")),
                    "polygon_source_pixels_json": json.dumps([
                        {"x": p["x"] * size["width_px"], "y": p["y"] * size["height_px"]}
                        for p in points], separators=(",", ":")),
                })
    failures = []
    for sid, row in comparison_by_id.items():
        for mode in ("ocr_all", "route_aware"):
            status = row[f"{mode}_status"]
            has_evidence = (sid, mode) in identities
            if has_evidence != (status in {"ok", "unexpected_success"}):
                raise ValueError("Handoff coverage differs from comparison statuses")
            if not has_evidence:
                failures.append({"id": sid, "mode": mode, "status": status,
                                 "error": row.get(f"{mode}_error")})
    if _sha(manifest_path) != manifest_sha256:
        raise ValueError("Manifest changed during geometry audit")
    report = {
        "dataset": manifest["dataset"], "version": manifest["version"], "split": manifest["split"],
        "manifest_sha256": manifest_sha256, "handoff_sha256": _sha(handoff_path),
        "manifest_binding": "verified_handoff_hash" if declared_manifest_sha256 is not None else "legacy_unbound_manifest",
        "interpretation": "source-frame/identity contract audit; not visual alignment, gold QA or accuracy",
        "cohort_samples": len(samples), "expected_runs": len(samples) * 2,
        "audited_runs": len(identities), "failed_runs": failures,
        "audited_pages": len(pages), "audited_blocks": len(blocks),
        "human_alignment_status": "pending_TV2_independent_QA_and_TV4_review",
        "pages": pages,
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "geometry-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    _csv(output / "pages.csv", pages)
    _csv(output / "blocks.csv", blocks)
    _csv(output / "failures.csv", failures)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.run_dir, args.manifest, args.output)
    print(f"Audited {report['audited_runs']}/{report['expected_runs']} runs; human alignment remains pending")


if __name__ == "__main__":
    main()
