"""Synthetic review challenges only; never an accuracy or participant dataset."""

import argparse
import hashlib
import io
import json
from pathlib import Path

from reportlab.pdfgen import canvas

from scripts.create_v2_demo import generate


def create(output):
    manifest = generate(output)
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(640, 820), invariant=1)
    pdf.setFont("Helvetica", 12)
    for index, line in enumerate([
        "INVOICE - SYNTHETIC REVIEW CHALLENGE",
        "Invoice template: 01GTKT0/001",
        "Invoice symbol: AA/??E",
        "Invoice number: 00001234 COPY",
        "Invoice date: 2026-10-23",
        "Seller name: Example Company",
        "Seller tax ID: 0101234567",
        "Seller address: 1 Sample Street",
        "Buyer name: Sample Buyer",
        "Buyer tax ID: N/A",
        "Currency: VND",
        "Notes: COPY is a print marker, not part of invoice number.",
        "The invoice symbol is obscured; keep it UNREADABLE.",
        "Fictional document. No hidden value should be guessed.",
    ]):
        pdf.drawString(35, 785 - index * 23, line)
    pdf.showPage()
    pdf.setFont("Helvetica", 12)
    for x, label in zip((35, 270, 345, 425, 520), ("Description", "Unit", "Quantity", "Unit price", "Amount")):
        pdf.drawString(x, 760, label)
    for index in range(12):
        for x, value in zip((35, 270, 345, 425, 520), (f"Office paper {index + 1}", "Ream", "2", "50000", "100000")):
            pdf.drawString(x, 725 - index * 30, value)
    for index, value in enumerate(("Subtotal: 1200000", "Total tax: 120000", "Grand total: 1320000")):
        pdf.drawString(35, 300 - index * 25, value)
    pdf.showPage()
    pdf.save()
    challenge = stream.getvalue()
    (output / "challenge.pdf").write_bytes(challenge)
    manifest["samples"].append(dict(id="challenge", path="challenge.pdf", condition="text_pdf_review_challenge",
        sha256=hashlib.sha256(challenge).hexdigest()))
    manifest["dataset"] = "tv6-synthetic-review-demo"
    manifest["version"] = "1.0"
    manifest["review_reference"] = {
        "invoice_number": "00001234", "invoice_symbol_status": "UNREADABLE",
        "seller_name": "Example Company", "line_description": "Office paper A4",
        "challenge_line_description": "Office paper 1",
        "policy": "Author-supplied workflow reference, not independently reviewed gold. Do not score accuracy.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    create(parser.parse_args().output)
