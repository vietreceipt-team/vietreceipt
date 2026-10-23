#!/usr/bin/env python3
"""Render synthetic SVG invoices to PDF/PNG and make deterministic OCR variants.

Run from repository root:
  python -m pip install svglib reportlab pillow pymupdf
  python scripts/build_synthetic_ocr_variants.py --root data/vietreceipt_synthetic_v0
"""
import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

import fitz  # PyMuPDF: rasterize generated PDFs to PNG
from PIL import Image, ImageFilter
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

SEED = 20261023


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def add_noise(im, rng):
    im = im.convert("RGB")
    px = im.load()
    # Deterministic sparse pixel noise; intentionally mild for OCR robustness testing.
    count = max(1, int(im.width * im.height * 0.003))
    for _ in range(count):
        x, y = rng.randrange(im.width), rng.randrange(im.height)
        delta = rng.choice((-28, -18, 18, 28))
        r, g, b = px[x, y]
        px[x, y] = tuple(max(0, min(255, c + delta)) for c in (r, g, b))
    return im


def pdf_to_png(pdf_path, png_path, scale=1.5):
    with fitz.open(pdf_path) as doc:
        if len(doc) != 1:
            raise RuntimeError(f"Expected one page in {pdf_path}, got {len(doc)}")
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        pix.save(str(png_path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/vietreceipt_synthetic_v0")
    ap.add_argument("--scale", type=float, default=1.5)
    args = ap.parse_args()

    root = Path(args.root)
    manifest = root / "manifest.csv"
    if not manifest.exists():
        raise SystemExit(f"Missing {manifest}; run from repository root.")
    with manifest.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("manifest.csv is empty")

    out = root / "rendered"
    pngdir, pdfdir, vdir = out / "png", out / "pdf", out / "variants"
    for d in (pngdir, pdfdir, vdir):
        d.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)
    outrows = []
    extra = [
        "parent_sample_id", "variant_id", "input_type", "degradation",
        "document_sha256", "ground_truth_sha256", "provenance",
    ]
    fields = list(dict.fromkeys(list(rows[0].keys()) + extra))

    for row in rows:
        sid = row["sample_id"]
        svg = Path(row["document_path"])
        label = Path(row["ground_truth_path"])
        if not svg.is_absolute():
            svg = Path.cwd() / svg
        if not label.is_absolute():
            label = Path.cwd() / label
        if not svg.exists() or not label.exists():
            raise SystemExit(f"Missing source/label for {sid}: {svg} / {label}")

        png = pngdir / f"{sid}.png"
        pdf = pdfdir / f"{sid}.pdf"
        drawing = svg2rlg(str(svg))
        if drawing is None:
            raise SystemExit(f"svglib could not parse SVG for {sid}: {svg}")
        renderPDF.drawToFile(drawing, str(pdf), showBoundary=0)
        pdf_to_png(pdf, png, args.scale)
        with Image.open(png) as im:
            base = im.convert("RGB")

        variants = {
            "clean": base.copy(),
            "blur": base.filter(ImageFilter.GaussianBlur(radius=1.2)),
            "noise": add_noise(base.copy(), rng),
            "skew": base.rotate(
                2.0, resample=Image.Resampling.BICUBIC,
                expand=False, fillcolor="white"
            ),
        }

        common = dict(row)
        for name, im in variants.items():
            vp = vdir / f"{sid}__{name}.png"
            ipdf = vdir / f"{sid}__{name}_image_only.pdf"
            im.save(vp, "PNG", optimize=True)
            im.save(ipdf, "PDF", resolution=150.0)
            for path, typ, prov in [
                (vp, "rendered_png" if name == "clean" else "png_image",
                 "synthetic_svg_render"),
                (ipdf, "image_only_pdf", "synthetic_render; image-only PDF"),
            ]:
                outrows.append({
                    **common, "parent_sample_id": sid,
                    "variant_id": path.stem,
                    "document_path": str(path).replace("\\", "/"),
                    "input_type": typ, "degradation": name,
                    "document_sha256": sha256(path),
                    "ground_truth_sha256": sha256(label),
                    "provenance": f"{prov}; deterministic_seed={SEED}",
                })

        outrows.append({
            **common, "parent_sample_id": sid,
            "variant_id": f"{sid}__vector_pdf",
            "document_path": str(pdf).replace("\\", "/"),
            "input_type": "vector_pdf", "degradation": "clean",
            "document_sha256": sha256(pdf),
            "ground_truth_sha256": sha256(label),
            "provenance": "synthetic_svg_to_pdf; verify text extraction before direct-text experiment",
        })

    outmf = out / "manifest.csv"
    with outmf.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(outrows)

    # Basic artifact/manifest QA. This does not evaluate OCR quality.
    missing = [r["document_path"] for r in outrows if not Path(r["document_path"]).exists()]
    duplicate_variants = len(outrows) - len({r["variant_id"] for r in outrows})
    report = {
        "dataset_family": "vietreceipt_synthetic",
        "dataset_snapshot": "v0.1-rendered",
        "source_sample_count": len(rows),
        "generated_manifest_rows": len(outrows),
        "missing_output_count": len(missing),
        "duplicate_variant_id_count": duplicate_variants,
        "variants": ["clean", "blur", "noise", "skew"],
        "layout_split": "Inherited from parent; all variants stay in parent's split",
        "vector_pdf_text_extraction_verified": False,
        "document_reader_outputs_included": False,
        "note": "Synthetic development artifacts only; not the independent final test set.",
    }
    (out / "qa_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Rendered {len(rows)} source invoices; generated {len(outrows)} manifest rows.")
    print(f"Manifest: {outmf}")
    print(f"QA report: {out / 'qa_report.json'}")
    print(f"Missing output files: {len(missing)}")
    print(f"Duplicate variant IDs: {duplicate_variants}")
    print("OCR predictions are not generated; run Document Reader separately.")
    if missing or duplicate_variants:
        raise SystemExit("QA FAILED: inspect rendered/qa_report.json")


if __name__ == "__main__":
    main()
