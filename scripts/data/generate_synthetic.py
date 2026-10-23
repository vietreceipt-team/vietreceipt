"""Generate source gold, visible text and reproducible invoice PDFs before augmentation."""

import argparse
import io
import random
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .common import HEADERS, ROOT, cell, dump, sha, write_csv, write_text

VERSION = "0.2.0"
LAYOUTS = {
    "corporate": ("train", 595, 842, 34, 16, "#183153", "left"),
    "retail": ("train", 440, 760, 22, 15, "#7b341e", "center"),
    "service": ("train", 595, 842, 44, 18, "#14532d", "left"),
    "table_heavy": ("validation", 842, 700, 30, 17, "#4338ca", "center"),
    "long_invoice": ("test", 595, 1100, 34, 16, "#374151", "left"),
    "minimal": ("test", 595, 842, 45, 19, "#111827", "right"),
}
LABELS = dict(
    zip(
        HEADERS,
        (
            "Mẫu số",
            "Ký hiệu",
            "Số hóa đơn",
            "Ngày lập",
            "Đơn vị bán hàng",
            "MST người bán",
            "Địa chỉ người bán",
            "Người mua",
            "MST người mua",
            "Cộng tiền hàng",
            "Tiền thuế GTGT",
            "Tổng thanh toán",
            "Tiền tệ",
        ),
    )
)
PRODUCTS = [
    ("Giấy in A4", "Ram", 65000),
    ("Bút bi xanh", "Cây", 5000),
    ("Sổ tay văn phòng", "Quyển", 18000),
    ("Dịch vụ in tài liệu", "Lần", 12000),
    ("Bìa hồ sơ", "Cái", 7000),
    ("Mực máy in", "Hộp", 145000),
]


def font_path(explicit=None):
    candidates = (
        [explicit]
        if explicit
        else [
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )
    for path in candidates:
        if path and Path(path).is_file():
            return Path(path)
    raise ValueError("Provide --font pointing to a Unicode TrueType font")


def make_gold(index, layout, seed):
    rng = random.Random(f"{seed}:{index}")
    sid = f"VRSYN2-{index:05d}"
    count = 12 if layout == "long_invoice" else rng.randint(1, 5)
    items = []
    for n in range(count):
        description, unit, price = rng.choice(PRODUCTS)
        quantity = rng.randint(1, 6)
        items.append(
            dict(
                line_id=f"{sid}-L{n + 1:02}",
                **{
                    key: cell(value)
                    for key, value in zip(
                        ("description", "unit", "quantity", "unit_price", "amount"),
                        (description, unit, quantity, price, quantity * price),
                    )
                },
            )
        )
    subtotal = sum(i["amount"]["normalized_value"] for i in items)
    rate = (0, 5, 8, 10)[(index - 1) % 4]
    tax = (subtotal * rate + 50) // 100
    values = dict(
        zip(
            HEADERS,
            (
                "1",
                f"C26T{index % 10}A",
                f"{index:08}",
                f"2026-{(index - 1) % 12 + 1:02}-{(index - 1) % 27 + 1:02}",
                ("CÔNG TY MẪU MINH AN", "CỬA HÀNG MẪU SAO VIỆT", "CÔNG TY MẪU HOA SEN")[
                    index % 3
                ],
                f"000{index:07}",
                f"{index} Đường Mẫu, Thành phố Hà Nội",
                None if index % 5 == 0 else "KHÁCH HÀNG THỬ NGHIỆM",
                None if index % 5 == 0 else f"000{index + 3000:07}",
                subtotal,
                tax,
                subtotal + tax,
                "VND",
            ),
        )
    )
    gold = dict(
        annotation_schema_version="2.0",
        receipt_id=str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"vietreceipt/{VERSION}/{seed}/{sid}")
        ),
        dataset_family="vietreceipt_synthetic",
        dataset_snapshot=VERSION,
        sample_id=sid,
        synthetic=True,
        split=LAYOUTS[layout][0],
        mapping_version="vietreceipt-source-gold-2.0",
        template_id=layout,
        parent_sample_id=None,
        fields={k: cell(v) for k, v in values.items()},
        line_items=items,
    )
    return gold, rate


def render_spec(gold, rate, font):
    """A single visible-text specification drives SVG, PDF and transcription."""
    layout = gold["template_id"]
    split, width, height, margin, step, color, align = LAYOUTS[layout]
    entries = []

    def add(key, text, x, y, size=10):
        entries.append(dict(key=key, text=text, x=x, y=y, size=size))

    title = "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
    tw = pdfmetrics.stringWidth(title, font, 16)
    tx = (
        margin
        if align == "left"
        else (width - tw) / 2
        if align == "center"
        else width - margin - tw
    )
    add("title", title, tx, 34, 16)
    y = 68
    identity = list(HEADERS[:9])
    if layout == "service":
        identity = list(HEADERS[4:9]) + list(HEADERS[:4])
    for k in identity:
        v = gold["fields"][k]["raw_value"]
        if v is not None:
            x = margin
            size = 10
            # Corporate identity uses separate invoice and seller/buyer panels;
            # the compact receipt and service forms retain a stacked identity.
            if layout == "corporate":
                if k in HEADERS[:4]:
                    x = width * 0.57
                    yy = 68 + list(HEADERS[:4]).index(k) * step
                else:
                    yy = 68 + list(HEADERS[4:9]).index(k) * step
                size = 8 if k in HEADERS[4:9] else 9
            elif layout == "table_heavy":
                x = margin if k in HEADERS[:4] else width * 0.46
                yy = (
                    68
                    + (
                        list(HEADERS[:4]).index(k)
                        if k in HEADERS[:4]
                        else list(HEADERS[4:9]).index(k)
                    )
                    * step
                )
            else:
                yy = y
            add("fields." + k, f"{LABELS[k]}: {v}", x, yy, size)
            y += step
    if layout in ("corporate", "table_heavy"):
        y = 68 + 5 * step
    if layout == "corporate":
        y += 24  # Keep the table clear of the two identity panels.
    y += 22
    fractions = (0, 0.46, 0.57, 0.67, 0.82)
    xs = [margin + (width - 2 * margin) * f for f in fractions]
    column_keys = ("description", "unit", "quantity", "unit_price", "amount")
    for k, label, x in zip(
        column_keys, ("Tên hàng / dịch vụ", "ĐVT", "SL", "Đơn giá", "Thành tiền"), xs
    ):
        add("column." + k, label, x, y, 9)
    y += 24
    for n, item in enumerate(gold["line_items"]):
        for k, x in zip(column_keys, xs):
            v = item[k]["raw_value"]
            text = (
                f"{v:,}".replace(",", ".") if k in ("unit_price", "amount") else str(v)
            )
            add(f"line_items.{n}.{k}", text, x, y, 9)
        y += 24 if layout != "table_heavy" else 28
    y += 18
    add("vat_rate", f"Thuế suất GTGT: {rate}%", margin, y)
    y += step
    summary_y = y
    for k in HEADERS[9:]:
        v = gold["fields"][k]["raw_value"]
        text = f"{v:,}".replace(",", ".") if isinstance(v, int) else str(v)
        summary_x = (
            width * 0.54
            if layout in ("corporate", "table_heavy", "minimal")
            else margin
        )
        add(
            "fields." + k,
            f"{LABELS[k]}: {text}",
            summary_x,
            y,
            11 if k == "total_amount" else 10,
        )
        y += step
    add(
        "disclaimer", "DỮ LIỆU GIẢ LẬP - KHÔNG CÓ GIÁ TRỊ THANH TOÁN", margin, y + 25, 8
    )
    if y + 40 > height:
        raise ValueError("Invoice exceeds page height")
    for e in entries:
        if (
            e["x"] + pdfmetrics.stringWidth(e["text"], font, e["size"])
            > width - margin + 1
        ):
            raise ValueError(f"Text exceeds page width: {e}")
    table_top = min(e["y"] for e in entries if e["key"].startswith("column.")) - 14
    table_bottom = (
        max(e["y"] for e in entries if e["key"].startswith("line_items.")) + 10
    )
    return dict(
        width=width,
        height=height,
        color=color,
        entries=entries,
        layout=layout,
        table_top=table_top,
        table_bottom=table_bottom,
        column_xs=xs,
        summary_y=summary_y,
        margin=margin,
    )


def render_pdf(spec, path, font):
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(spec["width"], spec["height"]), invariant=1)
    c.setTitle("VietReceipt synthetic development invoice")
    c.setStrokeColor(spec["color"])
    c.line(20, spec["height"] - 46, spec["width"] - 20, spec["height"] - 46)
    if spec["layout"] == "corporate":
        c.rect(24, spec["height"] - 166, spec["width"] - 48, 112, stroke=1, fill=0)
        c.line(
            spec["width"] * 0.55,
            spec["height"] - 54,
            spec["width"] * 0.55,
            spec["height"] - 166,
        )
    if spec["layout"] == "service":
        c.setFillColor(spec["color"])
        c.rect(16, 24, 8, spec["height"] - 80, stroke=0, fill=1)
    if spec["layout"] in ("table_heavy", "corporate"):
        top, bottom = spec["table_top"], spec["table_bottom"]
        left, right = spec["margin"] - 6, spec["width"] - spec["margin"] + 6
        c.rect(
            left, spec["height"] - bottom, right - left, bottom - top, stroke=1, fill=0
        )
        if spec["layout"] == "table_heavy":
            for x in spec["column_xs"][1:]:
                c.line(x - 6, spec["height"] - top, x - 6, spec["height"] - bottom)
            ys = sorted(
                {
                    e["y"] + 10
                    for e in spec["entries"]
                    if e["key"].startswith(("column.", "line_items."))
                }
            )
            for y in ys:
                c.line(left, spec["height"] - y, right, spec["height"] - y)
    c.setFillColor("#111111")
    for e in spec["entries"]:
        c.setFont(font, e["size"])
        c.drawString(e["x"], spec["height"] - e["y"], e["text"])
    c.showPage()
    c.save()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(stream.getvalue())


def generate(out, count=30, seed=20261023, font=None):
    if count < len(LAYOUTS):
        raise ValueError("At least six samples required to cover all layout families")
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError(
            "Output must be new/empty; never overwrite a versioned dataset"
        )
    fp = font_path(font)
    name = "TV2Unicode"
    pdfmetrics.registerFont(TTFont(name, str(fp)))
    rows = []
    for index in range(1, count + 1):
        layout = list(LAYOUTS)[(index - 1) % len(LAYOUTS)]
        gold, rate = make_gold(index, layout, seed)
        sid = gold["sample_id"]
        spec = render_spec(gold, rate, name)
        label = f"labels/{sid}.json"
        pdf = f"documents/{sid}.pdf"
        text = f"transcripts/{sid}.txt"
        dump(out / label, gold)
        dump(out / f"render_specs/{sid}.json", spec)
        write_text(out / text, "\n".join(e["text"] for e in spec["entries"]) + "\n")
        render_pdf(spec, out / pdf, name)
        svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{spec["width"]}" height="{spec["height"]}">',
            '<rect width="100%" height="100%" fill="white"/>',
        ]
        svg += [
            f'<text x="{e["x"]}" y="{e["y"]}" font-family="Arial,DejaVu Sans,sans-serif" font-size="{e["size"]}">{escape(e["text"])}</text>'
            for e in spec["entries"]
        ]
        write_text(out / f"documents/{sid}.svg", "\n".join(svg + ["</svg>"]) + "\n")
        rows.append(
            dict(
                sample_id=sid,
                base_document_id=sid,
                dataset_family=gold["dataset_family"],
                dataset_version=VERSION,
                original_sample_id=sid,
                source_type="text_pdf",
                synthetic="true",
                split=gold["split"],
                template_id=layout,
                layout_id=layout,
                parent_sample_id="",
                augmentation_type="clean",
                annotation_version="2.0",
                mapping_version=gold["mapping_version"],
                document_path=pdf,
                ground_truth_path=label,
                transcript_path=text,
                render_spec_path=f"render_specs/{sid}.json",
                document_sha256=sha(out / pdf),
                ground_truth_sha256=sha(out / label),
                transcript_sha256=sha(out / text),
                annotation_role="source_gold_unlinked",
                final_eligible="false",
            )
        )
    write_csv(out / "manifest.csv", rows)
    for split in ("train", "validation", "test"):
        write_csv(
            out / f"manifests/{split}_v2.csv", [r for r in rows if r["split"] == split]
        )
    dump(
        out / "generation.json",
        dict(
            generator_version=VERSION,
            seed=seed,
            font_sha256=sha(fp),
            font_name=fp.name,
            count=count,
            final_frozen=False,
            source_gold_verified_by_human=False,
            layouts={k: v[0] for k, v in LAYOUTS.items()},
        ),
    )
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=ROOT / "data/synthetic/v0.2.0")
    p.add_argument("--count", type=int, default=30)
    p.add_argument("--seed", type=int, default=20261023)
    p.add_argument("--font")
    a = p.parse_args()
    rows = generate(a.out, a.count, a.seed, a.font)
    print(
        f"Generated {len(rows)} development invoices; source gold is not evidence-linked."
    )


if __name__ == "__main__":
    main()
