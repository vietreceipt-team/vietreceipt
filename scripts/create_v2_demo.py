"""Fictional one-template demo, not unseen/frozen evaluation or accuracy evidence."""

import argparse
import hashlib
import io
import json
from pathlib import Path

from reportlab.pdfgen import canvas
from contextlib import closing
import pypdfium2 as pdfium
from reportlab.lib.utils import ImageReader


def render(data):
    with (
        pdfium.PdfDocument(data) as document,
        closing(document[0]) as page,
        closing(page.render(scale=2)) as bitmap,
    ):
        return bitmap.to_pil().convert("RGB")


def scan_pdf(image):
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(640, 820), invariant=1)
    pdf.drawImage(ImageReader(image), 0, 0, width=640, height=820)
    pdf.showPage()
    pdf.save()
    return stream.getvalue()


def generate(output):
    output.mkdir(parents=True, exist_ok=False)
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(640, 820), invariant=1)
    lines = [
        "INVOICE - SYNTHETIC DEMO ONLY",
        "Invoice template: 01GTKT0/001",
        "Invoice symbol: AA/26E",
        "Invoice number: 00001234",
        "Invoice date: 2026-10-23",
        "Seller name: Example Company",
        "Seller tax ID: 0101234567",
        "Seller address: 1 Sample Street",
        "Buyer name: Sample Buyer",
        "Buyer tax ID: 0201234567",
        "Currency: VND",
    ]
    pdf.setFont("Helvetica", 12)
    for index, text in enumerate(lines):
        pdf.drawString(35, 785 - index * 23, text)
    for x, text in zip(
        (35, 270, 345, 425, 520),
        ("Description", "Unit", "Quantity", "Unit price", "Amount"),
    ):
        pdf.drawString(x, 500, text)
    for x, text in zip(
        (35, 270, 345, 425, 520), ("Office paper A4", "Ream", "2", "50000", "100000")
    ):
        pdf.drawString(x, 470, text)
    for index, text in enumerate(
        ("Subtotal: 100000", "Total tax: 10000", "Grand total: 110000")
    ):
        pdf.drawString(35, 400 - index * 25, text)
    for x, text in zip((35, 270, 520), ("Tax rate", "Taxable amount", "Tax amount")):
        pdf.drawString(x, 280, text)
    for x, text in zip((35, 270, 520), ("10%", "100000", "10000")):
        pdf.drawString(x, 250, text)
    pdf.drawString(35, 180, "Notes: fictional document, not a real invoice")
    pdf.showPage()
    pdf.save()
    text = stream.getvalue()
    (output / "text.pdf").write_bytes(text)
    image = render(text)
    image.save(output / "photo.jpg", quality=90)
    (output / "scan.pdf").write_bytes(scan_pdf(image))
    samples = []
    for name, condition in (
        ("text.pdf", "text_pdf"),
        ("photo.jpg", "jpg"),
        ("scan.pdf", "scan_pdf"),
    ):
        samples.append(
            dict(
                id=condition,
                path=name,
                condition=condition,
                sha256=hashlib.sha256((output / name).read_bytes()).hexdigest(),
                review={"header": {"invoice_number": "DEMO-REVIEWED"}},
            )
        )
    manifest = dict(
        dataset="v2-synthetic-demo",
        version="1.0",
        split="demo",
        synthetic=True,
        provenance="Generated fictional invoice; three variants of ONE template. Workflow evidence only, not final evaluation.",
        samples=samples,
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    generate(p.parse_args().output)
