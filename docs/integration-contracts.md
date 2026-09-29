# Integration Contracts v2

This document supersedes the former five-field receipt contract.

## 1. Canonical header fields

```text
invoice_template_number
invoice_symbol
invoice_number
invoice_date
seller_name
seller_tax_id
seller_address
buyer_name
buyer_tax_id
subtotal
tax_amount
total_amount
currency
```

### Types

- identifiers/names/addresses/tax IDs/currency: string;
- invoice_date: ISO `YYYY-MM-DD`;
- monetary values: non-negative integer VND for the current core demo when currency is VND;
- invoice number/template/symbol remain strings to preserve leading zeros and formatting.

A field with status other than PRESENT has a null normalized/effective value.

## 2. Value status

- PRESENT
- NOT_PRESENT
- UNREADABLE
- AMBIGUOUS
- UNKNOWN

Missing, unreadable and ambiguous must never be collapsed into one null reason.

## 3. Line items

Each item has an internal `line_id` and may contain:

- description;
- unit;
- quantity;
- unit_price;
- amount;
- source OCR block IDs;
- review state.

The system must be able to represent a line that is partially unreadable. It must not silently drop a difficult line.

## 4. Tax breakdown

The schema may represent multiple tax groups. A tax rate is not forced to one global numeric rate when the source contains multiple or non-standard values.

## 5. OCR contract

OCR/PDF readers produce canonical ordered text blocks with:

- block ID;
- text;
- confidence when the engine supplies it;
- normalized 4-point polygon;
- reading order;
- source page.

Direct PDF text extraction and OCR should be adapted into this common evidence representation.

## 6. KIE contract

KIE consumes one canonical OCR/text-evidence result and targets `schemas/invoice-kie-result.v2.schema.json`. The existing `schemas/kie-result.schema.json` remains the legacy five-field runtime contract until migration is complete.

KIE output preserves:

- raw evidence;
- predicted value;
- normalized value;
- status;
- confidence/review metadata;
- source block IDs;
- extractor version;
- immutable run IDs.

## 7. Human corrections

Machine values are immutable. Corrections and confirmation are separate state.

Header corrections may use the existing field-correction pattern. Line-item correction must preserve both the machine row and the effective human-reviewed row.

## 8. Export

Confirmed export includes:

- invoice header table;
- line-item table linked by internal receipt/invoice ID;
- JSON representation;
- review/provenance status where needed.

CSV/XLSX must not serialize an entire multi-row item table into one opaque cell.

## 9. Compatibility

Legacy names are not canonical:

- `merchant_name` → `seller_name`
- `receipt_date` → `invoice_date`
- `invoice_id` → `invoice_number`
- `merchant_address` → `seller_address`

New code must use the canonical v2 names.

## 10. Implemented TV4 provider and required machine metadata

`extract_invoice(evidence: dict, *, kie_run_id: uuid.UUID) -> dict` is exposed as
`V2_KIE_CALLABLE=ai.kie.v2:extract_invoice`. It accepts OCRResult 1.3 or the TV3
`document-2.0` envelope with `pages[{page_index,evidence}]`. Pages are zero-based,
contiguous and share receipt/OCR run identity; block IDs are unique document-wide.

The shared V2 schema now resolves the omissions identified in issue #49:

- Every cell requires `raw_text`, `predicted_value`, `normalized_value`,
  `normalization`, `value_status`, `confidence`, `heuristic_score`, `score_version`,
  `machine_needs_review`, `review_reasons`, `review_policy_version`, `source_block_ids`.
- Root requires immutable `receipt_id`, `kie_run_id`, `source_ocr_run_id`,
  `extractor{name,version}`, `configuration{name,version}`, and versioned
  `consistency{version,tolerance_vnd,checks}` diagnostics.
- Each line requires `line_id` plus aggregate row-level source IDs, review flag,
  reasons and policy version in addition to its five cells. Partial rows are retained.
- PRESENT requires prediction, normalized value, normalization rule/version and
  source evidence. All other statuses have null normalized value/normalization.
- Baseline field confidence is null; its versioned heuristic score is not a
  probability. OCR `pdfium-text` sentinel 1.0 means N/A evidence confidence.
- Source membership/raw-text equality and run identity need the cross-record
  validator `ai.kie.v2.contract.validate_result`, not JSON Schema alone.

No human correction/effective/verified state is accepted by this machine schema.
Dependent V2 test producers must adopt these required additions; the V1 five-field
schema is unchanged. See [TV4 implementation guide](kie-v2.md) for exact rules,
provider references, synthetic examples and known limits.
