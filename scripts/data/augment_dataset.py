"""Render PDF inputs and controlled variants after the base-document split."""

import argparse
import random
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .common import dump, read_csv, resolve, sha, write_csv


def scan_pdf(image, path):
    # ReportLab invariant mode prevents timestamps/random IDs from changing hashes.
    c = canvas.Canvas(str(path), pagesize=image.size, invariant=1)
    c.drawImage(ImageReader(image), 0, 0, width=image.width, height=image.height)
    c.showPage()
    c.save()


def augment(root, scale=1.5, seed=20261023):
    root = Path(root).resolve()
    rows = read_csv(root / "manifest.csv")
    output = []
    variants_dir = root / "rendered"
    if variants_dir.exists():
        raise ValueError("rendered/ already exists; use a new dataset version")
    variants_dir.mkdir()
    for row in rows:
        path = resolve(root, row["document_path"])
        with pdfium.PdfDocument(path) as doc:
            page = doc[0]
            textpage = page.get_textpage()
            extracted = textpage.get_text_range()
            reference = resolve(root, row["transcript_path"]).read_text(
                encoding="utf-8"
            )
            if "".join(extracted.split()) != "".join(reference.split()):
                raise ValueError(
                    f"Text PDF differs from visible transcript: {row['sample_id']}"
                )
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert("RGB").copy()
            bitmap.close()
            textpage.close()
            page.close()
        rng = random.Random(f"{seed}:{row['sample_id']}")
        noise = image.copy()
        pixels = noise.load()
        for _ in range(int(noise.width * noise.height * 0.005)):
            x, y = rng.randrange(noise.width), rng.randrange(noise.height)
            pixels[x, y] = (rng.randrange(256),) * 3
        w, h = image.size
        # QUAD corners TL, BL, BR, TR: deterministic projective distortion.
        perspective = image.transform(
            image.size,
            Image.Transform.QUAD,
            (w * 0.025, h * 0.015, 0, h * 0.97, w * 0.98, h, w, h * 0.03),
            resample=Image.Resampling.BICUBIC,
            fillcolor="white",
        )
        variants = {
            "clean": (image, {}),
            "blur": (image.filter(ImageFilter.GaussianBlur(1.2)), {"radius": 1.2}),
            "noise": (noise, {"pixel_fraction": 0.005}),
            "rotation": (
                image.rotate(2, Image.Resampling.BICUBIC, fillcolor="white"),
                {"degrees": 2},
            ),
            "perspective": (
                perspective,
                {"quad_fraction": [0.025, 0.015, 0, 0.97, 0.98, 1, 1, 0.03]},
            ),
            "contrast": (ImageEnhance.Contrast(image).enhance(0.55), {"factor": 0.55}),
            "scan_like": (
                ImageOps.grayscale(noise).convert("RGB"),
                {"grayscale": True},
            ),
            "photo_like": (
                ImageEnhance.Brightness(perspective).enhance(0.82),
                {"brightness": 0.82},
            ),
        }
        output.append(
            dict(
                row,
                variant_id=row["sample_id"] + "__text_pdf",
                parent_sample_id=row["sample_id"],
            )
        )
        for kind, (im, params) in variants.items():
            stem = row["sample_id"] + "__" + kind
            for ext in ("png", "pdf"):
                relative = f"rendered/{stem}.{ext}"
                if ext == "png":
                    im.save(root / relative, "PNG")
                else:
                    scan_pdf(im, root / relative)
                output.append(
                    dict(
                        row,
                        variant_id=stem + "_" + ext,
                        parent_sample_id=row["sample_id"],
                        document_path=relative,
                        document_sha256=sha(root / relative),
                        source_type="image" if ext == "png" else "scanned_pdf",
                        augmentation_type=kind,
                    )
                )
            dump(
                root / f"rendered/{stem}.metadata.json",
                dict(
                    parent=row["sample_id"],
                    seed=seed,
                    augmentation_type=kind,
                    parameters=params,
                    split=row["split"],
                    template_id=row["template_id"],
                    scale=scale,
                ),
            )
    write_csv(root / "rendered_manifest.csv", output)
    for split in ("train", "validation", "test"):
        samples = [
            dict(
                id=r["variant_id"],
                path=r["document_path"],
                condition=r["augmentation_type"] + "_" + r["source_type"],
                reference=resolve(root, r["transcript_path"]).read_text(
                    encoding="utf-8"
                ),
                parent_sample_id=r["sample_id"],
                dataset_family=r["dataset_family"],
                template_id=r["template_id"],
                sha256=r["document_sha256"],
            )
            for r in output
            if r["split"] == split
        ]
        dump(
            root / f"tv3_{split}.json",
            dict(
                dataset={
                    "name": "vietreceipt_synthetic",
                    "version": rows[0]["dataset_version"],
                },
                split=split,
                frozen=False,
                purpose="development_only",
                samples=samples,
            ),
        )
    dump(
        root / "render_qa.json",
        dict(
            sample_count=len(output),
            text_pdf_verified=True,
            source_samples=len(rows),
            conditions=list(variants),
            final_frozen=False,
        ),
    )
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    a = p.parse_args()
    print(f"Created {len(augment(a.root))} file variants")


if __name__ == "__main__":
    main()
