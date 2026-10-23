#!/usr/bin/env python3
"""Generate a deterministic, synthetic VietReceipt v0 dataset.

Outputs SVG invoice documents, schema-v2 ground-truth JSON, and a CSV manifest.
No real customer/vendor data is used. Each layout family belongs to one split.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import uuid
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

SEED = 20261023
LAYOUT_SPLITS = {"layout_a": "train", "layout_b": "validation", "layout_c": "test"}
SELLERS = ["Cong ty Minh An", "Cua hang Sao Viet", "Doanh nghiep Hoa Sen"]
BUYERS = ["Cong ty Demo Ha Noi", "Van phong Mau", "Khach hang Thu Nghiem"]
ITEMS = [
    ("Giay in A4", "ream", Decimal("65000")),
    ("But bi xanh", "cai", Decimal("5000")),
    ("So tay", "quyen", Decimal("18000")),
    ("Dich vu in tai lieu", "lan", Decimal("12000")),
    ("Bia ho so", "cai", Decimal("7000")),
    ("Muc may in", "hop", Decimal("145000")),
]

def money(value: Decimal) -> str:
    return f"{value:,.0f}".replace(",", ".")

def field(value):
    return {
        "annotation_status": "PRESENT" if value is not None else "UNKNOWN",
        "raw_value": value,
        "normalized_value": value,
        "source_block_ids": [],
    }

def make_invoice(index: int, layout: str, rng: random.Random):
    sample_id = f"VRSYN-{index:03d}"
    seller = SELLERS[(index - 1) % len(SELLERS)]
    buyer = BUYERS[(index + 1) % len(BUYERS)]
    date = f"2026-{((index - 1) % 12) + 1:02d}-{((index - 1) % 27) + 1:02d}"
    items = []
    count = 1 + (index % 4)
    chosen = [ITEMS[(index + j) % len(ITEMS)] for j in range(count)]
    subtotal = Decimal("0")
    for line_no, (description, unit, unit_price) in enumerate(chosen, start=1):
        quantity = 1 + ((index + line_no) % 5)
        amount = unit_price * quantity
        subtotal += amount
        items.append({
            "line_id": f"{sample_id}-L{line_no:02d}",
            "description": field(description),
            "unit": field(unit),
            "quantity": field(quantity),
            "unit_price": field(int(unit_price)),
            "amount": field(int(amount)),
        })
    vat_rate = Decimal("0.10")
    tax = (subtotal * vat_rate).quantize(Decimal("1"))
    total = subtotal + tax
    values = {
        "seller_name": seller,
        "buyer_name": buyer,
        "invoice_number": f"HD-{index:04d}",
        "invoice_date": date,
        "subtotal": int(subtotal),
        "vat_rate": "10%",
        "tax_amount": int(tax),
        "total_amount": int(total),
    }
    labels = {
        "annotation_schema_version": "2.0",
        "receipt_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "vietreceipt-synthetic-v0/" + sample_id)),
        "dataset_family": "vietreceipt_synthetic",
        "dataset_snapshot": "v0.1",
        "sample_id": sample_id,
        "synthetic": True,
        "split": LAYOUT_SPLITS[layout],
        "mapping_version": "vietreceipt-canonical-v2",
        "template_id": layout,
        "parent_sample_id": None,
        "fields": {key: field(value) for key, value in values.items()},
        "line_items": items,
    }
    return values, items, labels, int(subtotal), int(tax), int(total)

def svg_document(sample_id, layout, values, items, subtotal, tax, total):
    # Layouts deliberately differ in heading alignment and table style.
    if layout == "layout_a":
        title_x, title_anchor, line_y = 48, "start", 132
        table_header = '<rect x="40" y="205" width="720" height="30" fill="#e7eef7"/>'
    elif layout == "layout_b":
        title_x, title_anchor, line_y = 400, "middle", 150
        table_header = '<rect x="40" y="222" width="720" height="30" fill="#eeeeee"/>'
    else:
        title_x, title_anchor, line_y = 65, "start", 112
        table_header = '<path d="M40 198 H760" stroke="#222" stroke-width="2"/>'
    header_y = 205 if layout == "layout_a" else 222 if layout == "layout_b" else 198
    row_y = header_y + 52
    lines = []
    for i, item in enumerate(items):
        y = row_y + i * 30
        desc = escape(item["description"]["raw_value"])
        qty = item["quantity"]["raw_value"]
        unit_price = money(Decimal(item["unit_price"]["raw_value"]))
        amount = money(Decimal(item["amount"]["raw_value"]))
        lines.append(f'<text x="48" y="{y}" font-size="13">{i+1}. {desc}</text>')
        lines.append(f'<text x="500" y="{y}" font-size="13" text-anchor="middle">{qty}</text>')
        lines.append(f'<text x="620" y="{y}" font-size="13" text-anchor="end">{unit_price}</text>')
        lines.append(f'<text x="752" y="{y}" font-size="13" text-anchor="end">{amount}</text>')
    summary_y = row_y + len(items) * 30 + 20
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{max(500, summary_y+145)}" viewBox="0 0 800 {max(500, summary_y+145)}">
<rect width="100%" height="100%" fill="white"/>
<g font-family="Arial, sans-serif" fill="#111">
<text x="{title_x}" y="42" text-anchor="{title_anchor}" font-size="23" font-weight="bold">HOA DON / INVOICE</text>
<text x="48" y="76" font-size="14" font-weight="bold">{escape(values['seller_name'])}</text>
<text x="48" y="98" font-size="12">Ma hoa don: {escape(values['invoice_number'])}</text>
<text x="48" y="118" font-size="12">Ngay: {escape(values['invoice_date'])}</text>
<text x="430" y="76" font-size="12">Khach hang: {escape(values['buyer_name'])}</text>
{table_header}
<text x="48" y="{header_y+20}" font-size="12" font-weight="bold">Mat hang / Dich vu</text>
<text x="500" y="{header_y+20}" text-anchor="middle" font-size="12" font-weight="bold">SL</text>
<text x="620" y="{header_y+20}" text-anchor="end" font-size="12" font-weight="bold">Don gia</text>
<text x="752" y="{header_y+20}" text-anchor="end" font-size="12" font-weight="bold">Thanh tien</text>
{''.join(lines)}
<path d="M430 {summary_y} H760" stroke="#444"/>
<text x="530" y="{summary_y+24}" font-size="13">Cong tien hang:</text><text x="752" y="{summary_y+24}" text-anchor="end" font-size="13">{money(Decimal(subtotal))} VND</text>
<text x="530" y="{summary_y+48}" font-size="13">Thue VAT (10%):</text><text x="752" y="{summary_y+48}" text-anchor="end" font-size="13">{money(Decimal(tax))} VND</text>
<text x="530" y="{summary_y+78}" font-size="16" font-weight="bold">Tong cong:</text><text x="752" y="{summary_y+78}" text-anchor="end" font-size="16" font-weight="bold">{money(Decimal(total))} VND</text>
<text x="48" y="{summary_y+110}" font-size="10" fill="#555">SYNTHETIC SAMPLE - NOT A REAL INVOICE - {sample_id} / {layout}</text>
</g></svg>'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/vietreceipt_synthetic_v0")
    parser.add_argument("--count", type=int, default=30)
    args = parser.parse_args()
    if args.count < 3:
        raise SystemExit("--count must be at least 3")
    root = Path(args.out)
    docs, labels_dir = root / "documents", root / "labels"
    docs.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.csv"
    rng = random.Random(SEED)
    rows = []
    errors = []
    for index in range(1, args.count + 1):
        layout = list(LAYOUT_SPLITS)[(index - 1) % len(LAYOUT_SPLITS)]
        values, items, labels, subtotal, tax, total = make_invoice(index, layout, rng)
        svg_path = docs / f"VRSYN-{index:03d}.svg"
        label_path = labels_dir / f"VRSYN-{index:03d}.json"
        svg_path.write_text(svg_document(f"VRSYN-{index:03d}", layout, values, items, subtotal, tax, total), encoding="utf-8")
        label_path.write_text(json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if subtotal + tax != total:
            errors.append(f"arithmetic mismatch: VRSYN-{index:03d}")
        rows.append({
            "sample_id": f"VRSYN-{index:03d}",
            "dataset_family": "vietreceipt_synthetic",
            "dataset_snapshot": "v0.1",
            "document_path": str(svg_path).replace("\\", "/"),
            "ground_truth_path": str(label_path).replace("\\", "/"),
            "source_type": "synthetic_svg",
            "quality": "clean",
            "layout_id": layout,
            "parent_sample_id": "",
            "synthetic": "true",
            "split": LAYOUT_SPLITS[layout],
            "mapping_version": "vietreceipt-canonical-v2",
        })
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Generated {len(rows)} synthetic invoices at {root}")
    print("Layout-disjoint split: layout_a=train, layout_b=validation, layout_c=test")
    print(f"Manifest: {manifest_path}")
    print("Documents are SVG; convert/render to PNG or PDF for OCR tests as needed.")

if __name__ == "__main__":
    main()
