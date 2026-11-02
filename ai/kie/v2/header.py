"""Header candidate extraction from canonical positioned evidence."""

import re
from dataclasses import replace

from .cells import Candidate
from .config import HEADER_FIELDS
from .evidence import same_row
from .normalization import folded, text

LABELS = {
    "invoice_template_number": r"mau so|invoice template(?: number)?",
    "invoice_symbol": r"ky hieu|invoice symbol|serial",
    "invoice_number": r"so hoa don|so\s*phieu|s\s*phieu|invoice (?:number|no\.?)|so(?:\s*\(no\.?\))?",
    "invoice_date": r"ngay lap(?: hoa don)?|ngay hoa don|invoice date|date|ngay",
    "seller_name": r"(?:ten )?(?:don vi ban hang|nguoi ban|ben ban)|seller(?: name)?",
    "buyer_name": r"(?:ho ten )?nguoi mua(?: hang)?|(?:ten )?(?:don vi mua hang|ben mua)|buyer(?: name)?|khach hang|bill to|to(?=\s*:)",
    "seller_tax_id": r"(?:ma so thue|mst)(?: nguoi ban| ben ban)|seller tax (?:id|code)",
    "buyer_tax_id": r"(?:ma so thue|mst)(?: nguoi mua| ben mua)|buyer tax (?:id|code)",
    "seller_address": r"dia chi (?:nguoi ban|ben ban)|seller address",
    "subtotal": r"cong tien hang|tien hang|tong (?:tien )?truoc thue|tam tinh|subtotal|sub total",
    "tax_amount": r"tong tien thue(?: gtgt)?|tien thue(?: gtgt)?|tax amount|total tax|vat amount",
    "total_amount": r"tong cong(?: tien thanh toan)?|tong tien thanh toan|tong thanh toan|tong(?=\s*:|$)|grand total|total(?: amount)?",
    "currency": r"don vi tien te|loai tien|currency",
}
GENERIC = {
    "tax_id": r"ma so thue|mst|tax\s*(?:id|code)",
    "address": r"dia chi|address|d\s*c\.?",
    "name": r"ten don vi|company name",
}
CURRENCY_PATTERN = re.compile(
    r"(?<!\w)(?:VND|VNĐ|USD|EUR|GBP|JPY|CNY|đ)(?!\w)|[₫$€¥]", re.IGNORECASE
)


def label_match(value, patterns):
    normalized = text(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value))
    matches = []
    for field, pattern in patterns.items():
        match = re.match(
            rf"^(?:{pattern})(?=\s|[:#：]|\d|$)\s*[:#：]?\s*", folded(normalized)
        )
        if match:
            matches.append((match.end(), field))
    if not matches:
        return None
    end, field = max(matches)
    return field, normalized[end:]


def header_candidates(blocks, excluded):
    result = {field: [] for field in HEADER_FIELDS}
    anchors = []
    # A unique company letterhead above INVOICE supplies a seller candidate.
    # Preserve this inferred role for explicit review after selection.
    titles = [
        b
        for b in blocks
        if folded(b.text) == "invoice"
        or folded(b.text).replace(" ", "").startswith("hoadon")
    ]
    letterheads = [
        b
        for b in blocks
        if any(b.page == t.page and b.bottom < t.top for t in titles)
        and re.search(
            r"\b(?:company|corporation|limited|ltd|jsc)\b|^cong ty", folded(b.text)
        )
        and not label_match(b.text, GENERIC)
        and not label_match(b.text, LABELS)
    ]
    if len(letterheads) == 1:
        head = letterheads[0]
        sources = [head]
        for other in sorted(blocks, key=lambda b: (b.page, b.top)):
            previous = sources[-1]
            if (
                other.page == head.page
                and 0 <= other.top - previous.bottom <= 1.2 * previous.height
                and head.left - head.height <= other.left
                and other.right <= head.right + head.height
                and other not in titles
                and not label_match(other.text, GENERIC)
                and not label_match(other.text, LABELS)
                and not re.match(r"^(?:dt|tel|phone|attn)\b", folded(other.text))
            ):
                sources.append(other)
                break
        result["seller_name"].append(
            Candidate(" ".join(b.text for b in sources), tuple(sources))
        )
        anchors.append(("seller", head))
    for block in blocks:
        match = label_match(block.text, LABELS)
        if (
            block.block_id not in excluded
            and match
            and match[0] in {"seller_name", "buyer_name"}
        ):
            anchors.append((match[0].split("_")[0], block))
    for block in blocks:
        if block.block_id in excluded:
            continue
        match = label_match(block.text, LABELS)
        generic = label_match(block.text, GENERIC) if match is None else None
        explicit = True
        context = []
        if generic:
            suffix, value = generic
            # Bank remittance fields do not identify the invoice seller/buyer.
            if any(
                b.page == block.page
                and b.top < block.top
                and re.match(r"^(?:please remit|beneficiary|bank\s*:)", folded(b.text))
                for b in blocks
            ):
                continue
            # Relative section geometry handles side-by-side roles even when
            # reading order interleaves seller and buyer blocks.
            nearby = [
                (
                    abs(block.left - anchor.left) + abs(block.top - anchor.top),
                    role,
                    anchor,
                )
                for role, anchor in anchors
                if anchor.page == block.page
                and anchor.top <= block.top
                and anchor.block_id != block.block_id
            ]
            nearby.sort(key=lambda item: (item[0], item[2].reading_order))
            unclear = (
                len(nearby) > 1
                and nearby[0][1] != nearby[1][1]
                and abs(nearby[0][0] - nearby[1][0]) < block.height
            )
            if nearby and not unclear:
                _, role, role_block = nearby[0]
                field = f"{role}_{suffix}"
                context = [role_block]
                match = (field, value)
            elif suffix == "tax_id":
                # Preserve unassigned tax evidence for both roles, never guess seller.
                for field in ("seller_tax_id", "buyer_tax_id"):
                    result[field].append(
                        Candidate(value, (block,), explicit_role=False)
                    )
        if match:
            field, value = match
            if field not in result:
                continue
            sources = context + [block]
            if not value:
                neighbors = [
                    b
                    for b in blocks
                    if b.block_id not in excluded
                    and b.block_id != block.block_id
                    and same_row(b, block)
                    and b.left >= block.right
                    and not label_match(b.text, LABELS)
                    and not label_match(b.text, GENERIC)
                ]
                if neighbors:
                    nearest = min(neighbors, key=lambda b: (b.left, b.reading_order))
                    value = nearest.text
                    sources.append(nearest)
                    if field in {"invoice_number", "invoice_date"}:
                        for following in sorted(neighbors, key=lambda b: b.left):
                            if (
                                following.left >= sources[-1].right
                                and following.left - sources[-1].right
                                <= 1.5 * sources[-1].height
                            ):
                                value += " " + following.text
                                sources.append(following)
                    value = re.sub(r"^\s*[:#：]\s*", "", value)
            # The generic date label retains its word form for explicit component dates.
            if field == "invoice_date" and "thang" in folded(value):
                value = "ngày " + value
            numeric_date = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
            if (
                field == "invoice_date"
                and numeric_date
                and any(
                    t.page == block.page
                    and folded(t.text).replace(" ", "").startswith("hoadon")
                    for t in titles
                )
            ):
                day, month, year = numeric_date.groups()
                value = f"ngày {day} tháng {month} năm {year}"
            if field in {"buyer_name", "seller_name", "seller_address"} and value:
                previous = sources[-1]
                for neighbor in sorted(blocks, key=lambda b: (b.page, b.top, b.left)):
                    if (
                        neighbor.page == previous.page
                        and neighbor.block_id not in excluded
                        and 0 <= neighbor.top - previous.bottom <= 1.1 * previous.height
                        and (
                            abs(neighbor.left - previous.left) < previous.height
                            or field == "seller_address"
                            and previous.left <= neighbor.left <= previous.right
                            and neighbor.right <= previous.right + previous.height
                        )
                        and not label_match(neighbor.text, LABELS)
                        and not label_match(neighbor.text, GENERIC)
                        and not re.match(
                            r"^(?:attn|contract|invoice|bank|beneficiary|dt|tel)(?=\W|\d|$)",
                            folded(neighbor.text),
                        )
                    ):
                        value += " " + neighbor.text
                        sources.append(neighbor)
                        previous = neighbor
            result[field].append(
                Candidate(value, tuple(dict.fromkeys(sources)), explicit)
            )
        for marker in CURRENCY_PATTERN.finditer(block.text):
            result["currency"].append(Candidate(marker.group(), (block,)))
    vn_titles = [
        t for t in titles if folded(t.text).replace(" ", "").startswith("hoadon")
    ]
    if not result["currency"] and vn_titles and result["total_amount"]:
        if all(
            re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", c.value)
            for c in result["total_amount"]
        ):
            result["currency"].append(Candidate("VND", (vn_titles[0],)))
    return result


def extract_header_candidates(blocks, *, excluded_block_ids, region_hints=None):
    """Return all baseline candidates, optionally favoring likely field regions.

    region_hints is the existing table reconstruction output. It is an internal
    signal only: a misplaced table boundary cannot suppress a candidate.
    """
    result = header_candidates(blocks, excluded_block_ids)
    if region_hints is None:
        return result
    table_start = {}
    for _, columns, _ in region_hints:
        for block in columns.values():
            table_start[block.page] = min(table_start.get(block.page, 1), block.top)
    top_fields = set(HEADER_FIELDS) - {
        "subtotal",
        "tax_amount",
        "total_amount",
        "currency",
    }
    bottom_fields = {"subtotal", "tax_amount", "total_amount"}
    for field in top_fields | bottom_fields:
        candidates = result[field]
        if len(candidates) < 2:
            continue

        def preferred(candidate):
            first = candidate.blocks[0]
            boundary = table_start.get(first.page, 0.5)
            return first.top < boundary if field in top_fields else first.top > boundary

        if not any(preferred(c) for c in candidates):
            continue
        result[field] = [
            c if preferred(c) else replace(c, layout_penalty=0.12) for c in candidates
        ]
    return result
