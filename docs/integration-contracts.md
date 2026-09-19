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

KIE consumes one canonical OCR/text-evidence result and emits `schemas/kie-result.schema.json`.

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
