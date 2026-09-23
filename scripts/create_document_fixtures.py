"""Generate public-safe synthetic diagnostics; never a frozen evaluation dataset."""

from contextlib import closing

import argparse
import io
import json
from pathlib import Path

import pypdfium2 as pdfium
import numpy as np
from PIL import Image, ImageFilter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


LINES = [
    "HOÁ ĐƠN THỬ NGHIỆM - KHÔNG CÓ GIÁ TRỊ",
    "CÔNG TY MẪU VIETRECEIPT",
    "Mã số thuế: 0000000000",
    "Số hoá đơn: 00001234",
    "Ngày lập: 24/09/2026",
    "Người mua: KHÁCH HÀNG MẪU",
    "Tên hàng        Đơn vị        Số lượng        Đơn giá        Thành tiền",
    "Giấy in A4        Ram        2        50.000        100.000",
    "Bút bi        Cây        3        10.000        30.000",
    "Cộng tiền hàng: 130.000",
    "Thuế GTGT: 13.000",
    "Tổng thanh toán: 143.000 VND",
]


def make_text_pdf(lines=LINES, *, font_path=None, pages=1):
    if font_path:
        pdfmetrics.registerFont(TTFont("FixtureUnicode", str(font_path)))
        font = "FixtureUnicode"
    else:
        font = "Helvetica"
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(640, 820), invariant=1)
    for page in range(pages):
        c.setFont(font, 14)
        for index, line in enumerate(lines):
            c.drawString(35, 775 - index * 48, line)
        c.showPage()
    c.save()
    return stream.getvalue()


def render(data):
    with (
        pdfium.PdfDocument(data) as doc,
        closing(doc[0]) as page,
        closing(page.render(scale=2)) as bitmap,
    ):
        return bitmap.to_pil().convert("RGB")


def scan_pdf(image):
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(640, 820), invariant=1)
    c.drawImage(ImageReader(image), 0, 0, width=640, height=820)
    c.showPage()
    c.save()
    return stream.getvalue()


def generate(output, font_path):
    output.mkdir(parents=True, exist_ok=True)
    text = make_text_pdf(font_path=font_path)
    (output / "text.pdf").write_bytes(text)
    image = render(text)
    image.save(output / "clean.png")
    image.save(output / "photo.jpg", quality=65)
    image.filter(ImageFilter.GaussianBlur(1.3)).save(output / "blur.png")
    pixels = np.asarray(image).astype(np.float32)
    noise = np.random.default_rng(48).normal(0, 12, pixels.shape)
    Image.fromarray(np.clip(pixels + noise, 0, 255).astype(np.uint8)).save(
        output / "noise.png"
    )
    image.transform(
        image.size,
        Image.Transform.PERSPECTIVE,
        (1, 0.035, -20, 0.015, 1, -10, 0.00002, 0.000015),
        Image.Resampling.BICUBIC,
        fillcolor="white",
    ).save(output / "perspective.png")
    for angle in (90, 180, 270):
        image.rotate(-angle, expand=True).save(output / f"rotation-{angle}.png")
    scan = scan_pdf(image)
    (output / "scan.pdf").write_bytes(scan)
    with pdfium.PdfDocument(text) as doc, pdfium.PdfDocument(scan) as scanned:
        doc.import_pages(scanned)
        doc.save(output / "mixed.pdf")
    (output / "corrupt.pdf").write_bytes(b"%PDF-1.7\ncorrupt")
    rows = []
    for name, condition in [
        ("text.pdf", "text_pdf"),
        ("clean.png", "clean"),
        ("photo.jpg", "photo_like"),
        ("blur.png", "blur"),
        ("noise.png", "noise"),
        ("perspective.png", "perspective"),
        ("scan.pdf", "scan_like"),
        ("mixed.pdf", "mixed_pdf"),
    ]:
        rows.append(
            {
                "id": name.replace(".", "-"),
                "path": name,
                "condition": condition,
                "reference": " ".join(LINES * (2 if name == "mixed.pdf" else 1)),
            }
        )
    for angle in (90, 180, 270):
        rows.append(
            {
                "id": f"rotation-{angle}",
                "path": f"rotation-{angle}.png",
                "condition": "rotation",
                "reference": " ".join(LINES),
            }
        )
    rows.append(
        {
            "id": "corrupt",
            "path": "corrupt.pdf",
            "condition": "invalid",
            "expected_error": "PDF_READ_FAILED",
        }
    )
    manifest = {
        "dataset": "tv3-synthetic-diagnostics",
        "version": "1.0",
        "split": "development",
        "provenance": "Generated fictional invoice; all variants share one template. Not final test or generalization evidence.",
        "samples": rows,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--font",
        type=Path,
        required=True,
        help="Unicode TTF, e.g. DejaVuSans.ttf or Arial.ttf",
    )
    args = parser.parse_args()
    generate(args.output, args.font)


if __name__ == "__main__":
    main()
