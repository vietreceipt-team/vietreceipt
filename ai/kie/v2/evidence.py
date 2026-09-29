"""Engine-independent, immutable spatial evidence adapter."""

import json
from dataclasses import dataclass

from ai.kie.contract import validate_ocr_result


@dataclass(frozen=True)
class Block:
    block_id: str
    page: int
    reading_order: int
    text: str
    polygon: tuple[tuple[float, float], ...]
    confidence: float
    evidence_confidence: float | None

    @property
    def left(self):
        return min(p[0] for p in self.polygon)

    @property
    def right(self):
        return max(p[0] for p in self.polygon)

    @property
    def top(self):
        return min(p[1] for p in self.polygon)

    @property
    def bottom(self):
        return max(p[1] for p in self.polygon)

    @property
    def height(self):
        return self.bottom - self.top


def flatten(evidence: dict) -> list[Block]:
    # JSON Schema does not reject every nonfinite Python float on its own.
    json.dumps(evidence, allow_nan=False)
    if evidence.get("schema_version") == "document-2.0":
        if set(evidence) != {"schema_version", "receipt_id", "ocr_run_id", "pages"}:
            raise ValueError("Unexpected document envelope keys")
        pages = evidence["pages"]
        if not isinstance(pages, list) or not pages:
            raise ValueError("Document pages must be a nonempty array")
    else:
        pages = [{"page_index": 0, "evidence": evidence}]
    blocks = []
    seen = set()
    for index, page in enumerate(pages):
        if (
            set(page) != {"page_index", "evidence"}
            or type(page["page_index"]) is not int
            or page["page_index"] != index
        ):
            raise ValueError("Page indexes must be zero-based and contiguous")
        source = page["evidence"]
        validate_ocr_result(source)
        for key in ("receipt_id", "ocr_run_id"):
            if source[key] != evidence[key]:
                raise ValueError("Page receipt/run identity mismatch")
        for item in sorted(source["blocks"], key=lambda b: b["reading_order"]):
            if any(
                not (
                    ord(c) in (9, 10, 13)
                    or 0x20 <= ord(c) <= 0xD7FF
                    or 0xE000 <= ord(c) <= 0xFFFD
                    or 0x10000 <= ord(c) <= 0x10FFFF
                )
                for c in item["text"]
            ):
                raise ValueError("Source text cannot be transported by TV5 JSON/XLSX")
            if item["block_id"] in seen:
                raise ValueError("Duplicate block ID across document")
            seen.add(item["block_id"])
            points = tuple((p["x"], p["y"]) for p in item["polygon"])
            block = Block(
                item["block_id"],
                index,
                item["reading_order"],
                item["text"],
                points,
                item["confidence"],
                None
                if source["engine"]["name"] == "pdfium-text"
                else item["confidence"],
            )
            if block.height <= 0 or block.right <= block.left:
                raise ValueError("Degenerate source polygon")
            blocks.append(block)
    return blocks


def same_row(a: Block, b: Block, overlap: float = 0.35) -> bool:
    return a.page == b.page and (
        min(a.bottom, b.bottom) - max(a.top, b.top) >= overlap * min(a.height, b.height)
    )
