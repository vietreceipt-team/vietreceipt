# Shared Integration Contracts v1

The machine-readable definitions are in `schemas/`. This document fixes semantics that JSON Schema alone cannot explain.

## Shared conventions

| Concern | Convention |
| --- | --- |
| IDs | Backend entities use UUIDs; OCR block IDs are opaque strings unique within one receipt, e.g. `block_12` |
| Time | RFC 3339 UTC, suffix `Z` |
| Encoding | UTF-8 |
| Confidence | Number from `0.0` to `1.0`; never percentages |
| Missing value | JSON `null`; never empty string, `"unknown"`, `"N/A"` or invented data |
| Money | Integer VND, no separator, e.g. `325000` |
| Date | ISO `YYYY-MM-DD` after normalization |
| Coordinates | Normalized `[0,1]`, origin at image top-left, x grows right, y grows down |
| Unknown extra fields | Rejected by v1 schemas (`additionalProperties: false`) |
| Schema version | Exact string `1.0` in OCR/KIE documents |

## OCR input

The worker invokes OCR with:

```json
{
  "receipt_id": "31915ef1-6fb4-4e7d-b6f5-53be51c50e3d",
  "image_path": "/private/tmp/31915ef1/receipt.jpg"
}
```

`image_path` is an internal temporary path and is never exposed through the public API or persisted as the image identity.

## OCR output

Example conforming to `ocr-result.schema.json`:

```json
{
  "schema_version": "1.0",
  "receipt_id": "31915ef1-6fb4-4e7d-b6f5-53be51c50e3d",
  "engine": {"name": "paddleocr", "version": "3.0.0"},
  "image": {"width_px": 1080, "height_px": 1920},
  "blocks": [
    {
      "block_id": "block_12",
      "text": "TỔNG TIỀN",
      "confidence": 0.96,
      "polygon": [
        {"x": 0.083, "y": 0.323},
        {"x": 0.239, "y": 0.323},
        {"x": 0.239, "y": 0.344},
        {"x": 0.083, "y": 0.344}
      ],
      "reading_order": 12
    }
  ],
  "average_confidence": 0.96,
  "duration_ms": 842
}
```

OCR guarantees:

- `blocks` may be empty but is never `null`.
- `text` is trimmed Unicode text and is never an empty string.
- Polygon points are ordered clockwise starting near the top-left of the detected text region.
- `reading_order` is unique within a receipt and begins at zero.
- Engine-specific debug objects do not cross the adapter boundary.

## KIE input

KIE receives the entire OCR result unchanged. It may use text, reading order, polygons and confidence but cannot assume any particular OCR engine.

## KIE output

Example conforming to `kie-result.schema.json`:

```json
{
  "schema_version": "1.0",
  "receipt_id": "31915ef1-6fb4-4e7d-b6f5-53be51c50e3d",
  "extractor": {"name": "rule-layout-v1", "version": "0.1.0"},
  "fields": {
    "merchant": {
      "raw_text": "WINMART+",
      "normalized_value": "WINMART+",
      "confidence": 0.98,
      "source_block_ids": ["block_0"]
    },
    "date": {
      "raw_text": "08/08/2026",
      "normalized_value": "2026-08-08",
      "confidence": 0.91,
      "source_block_ids": ["block_2"]
    },
    "total": {
      "raw_text": "325.OOO VND",
      "normalized_value": 325000,
      "currency": "VND",
      "confidence": 0.71,
      "source_block_ids": ["block_5"]
    },
    "invoice_id": {
      "raw_text": "SỐ HĐ: 001238",
      "normalized_value": "001238",
      "confidence": 0.84,
      "source_block_ids": ["block_3"]
    },
    "address": {
      "raw_text": "12 NGUYỄN TRÃI",
      "normalized_value": "12 NGUYỄN TRÃI",
      "confidence": 0.94,
      "source_block_ids": ["block_1"]
    }
  },
  "duration_ms": 35
}
```

KIE guarantees:

- All five field keys are required.
- If no acceptable candidate exists: `raw_text=null`, `normalized_value=null`, `confidence=0`, `source_block_ids=[]`.
- `source_block_ids` contains only IDs from the input OCR result.
- `invoice_id` remains a string so leading zeroes are preserved.
- `total.normalized_value` is an integer; KIE does not return formatted strings such as `"325.000đ"`.
- Field confidence expresses KIE's confidence in the normalized business value, not merely OCR confidence.

## Required compatibility decisions with current module READMEs

| Topic | Current module README | Proposed contract v1 | Reason |
| --- | --- | --- | --- |
| Raw field name | KIE uses `raw_value` | `raw_text` | Matches project proposal and states that the value is source OCR text |
| Total type | KIE example uses `"325000"` | `325000` integer | Reliable range queries, sums and dashboard calculations |
| OCR reference | KIE uses `source_block_id` | `source_block_ids` array | Address/merchant may span multiple OCR blocks |
| Block ID | KIE example uses `block_12` | Opaque string | Avoids forcing OCR to generate UUIDs; unique within a receipt is enough |
| Bounding geometry | OCR says bounding box | Four-point normalized polygon | Supports rotated text and stable frontend scaling |

OCR and KIE owners must accept or propose a replacement for each row before the contract is marked final.

## Review-level calculation

Backend derives display classification from KIE confidence:

| Confidence | Review level |
| --- | --- |
| `< 0.60` | `NEEDS_REVIEW` |
| `0.60 <= c < 0.85` | `LOW_CONFIDENCE` |
| `>= 0.85` | `LIKELY_CORRECT` |

A `null` value always receives `NEEDS_REVIEW` regardless of score.

## Public API error envelope

```json
{
  "error": {
    "code": "RECEIPT_STATE_CONFLICT",
    "message": "Receipt must be in NEEDS_REVIEW before verification.",
    "details": {"current_status": "PROCESSING"},
    "request_id": "f89c3315-a7ce-4ddc-a5d2-b076d73a65c4"
  }
}
```

Rules:

- `code` is stable and machine-readable.
- `message` is safe for end users.
- `details` is optional and must contain no stack trace or secret.
- Every API response includes `X-Request-ID`; errors repeat it in the body.

## Versioning rule

- Compatible additions require a minor contract revision and must remain optional.
- Removing/renaming a field, changing its type or changing coordinate semantics requires a new major schema/API version.
- Any contract change must update schemas, examples, OpenAPI and consumer tests in one Pull Request.
