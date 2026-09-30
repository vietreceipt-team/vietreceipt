"""Hand-authored synthetic test doubles. NOT frozen gold or thesis results."""

from uuid import UUID

RECEIPT = "00000000-0000-4000-8000-000000000049"
OCR_RUN = "00000000-0000-4000-8000-000000000055"
KIE_RUN = UUID("00000000-0000-4000-8000-000000000053")


def evidence(entries, *, prefix="p0", engine="synthetic-test-double"):
    blocks = []
    for index, entry in enumerate(entries):
        value, x, y = entry[:3]
        width = entry[3] if len(entry) > 3 else 0.13
        blocks.append(
            {
                "block_id": f"{prefix}_b{index}",
                "text": value,
                "confidence": 0.98,
                "polygon": [
                    {"x": x, "y": y},
                    {"x": x + width, "y": y},
                    {"x": x + width, "y": y + 0.014},
                    {"x": x, "y": y + 0.014},
                ],
                "reading_order": index,
            }
        )
    return {
        "schema_version": "1.3",
        "receipt_id": RECEIPT,
        "ocr_run_id": OCR_RUN,
        "engine": {"name": engine, "version": "synthetic-1"},
        "image": {"width_px": 1000, "height_px": 1400},
        "blocks": blocks,
        "average_confidence": 0.98,
        "duration_ms": 0,
    }


def invoice(*, rows=None, unit=True, total="108000", tax_groups=False):
    entries = [
        (value, 0.05, 0.02 + index * 0.027, 0.6)
        for index, value in enumerate(
            [
                "Mẫu số: 01GTKT0/001",
                "Ký hiệu: AA/26E",
                "Số hóa đơn: 0000049",
                "Ngày lập: 19/09/2026",
                "Đơn vị bán hàng: Công ty Tổng Hợp Mẫu",
                "MST: 0101 234 567",
                "Địa chỉ: 1 Đường Mẫu, Thành phố Mẫu",
                "Người mua hàng: Công ty Khách Mẫu",
                "MST: 0201234567",
                "Đơn vị tiền tệ: VND",
            ]
        )
    ]
    xs = [0.05, 0.40, 0.53, 0.67, 0.84]
    headers = ["Tên hàng", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền"]
    entries.extend((v, x, 0.34) for v, x in zip(headers, xs) if unit or v != "ĐVT")
    rows = [["Dịch vụ mẫu", "gói", "2", "50000", "100000"]] if rows is None else rows
    for index, row in enumerate(rows):
        entries.extend(
            (v, x, 0.38 + index * 0.045)
            for v, x in zip(row, xs)
            if v is not None and (unit or x != 0.4)
        )
    entries.extend(
        [
            ("Cộng tiền hàng: 100000", 0.05, 0.70, 0.6),
            ("Tổng tiền thuế: 8000", 0.05, 0.74, 0.6),
            (f"Tổng cộng: {total}", 0.05, 0.78, 0.6),
            ("Khách đưa: 200000", 0.05, 0.82, 0.6),
        ]
    )
    if tax_groups:
        entries.extend(
            [
                ("Thuế suất", 0.05, 0.86),
                ("Tiền tính thuế", 0.40, 0.86),
                ("Tiền thuế", 0.75, 0.86),
                ("8%", 0.05, 0.89),
                ("100000", 0.40, 0.89),
                ("8000", 0.75, 0.89),
            ]
        )
    return evidence(entries)


def document(*pages):
    return {
        "schema_version": "document-2.0",
        "receipt_id": RECEIPT,
        "ocr_run_id": OCR_RUN,
        "pages": [{"page_index": i, "evidence": page} for i, page in enumerate(pages)],
    }
