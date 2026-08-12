# Shared Integration Contracts v1.3

The machine-readable definitions are in `schemas/`. This document fixes semantics that JSON Schema alone cannot explain.

## Shared conventions

| Concern | Convention |
| --- | --- |
| Entity IDs | Receipt, field, correction and run IDs are UUID strings |
| OCR block ID | Opaque string unique within one OCR run, e.g. `block_12` |
| Time | RFC 3339 UTC, suffix `Z` |
| Encoding | UTF-8 |
| Confidence | Number from `0.0` to `1.0`; never a percentage |
| Missing value | JSON `null`; never empty string, `"unknown"`, `"N/A"` or invented data |
| Money | Integer VND after safe normalization, e.g. `325000` |
| Date | ISO `YYYY-MM-DD` after safe normalization |
| Coordinates | Proposed normalized `[0,1]`, origin at image top-left, x right, y down; pending OCR sign-off |
| Unknown properties | Rejected by v1.3 schemas (`additionalProperties: false`) |
| Schema version | Exact string `1.3` in OCR/KIE documents |

## Canonical field names

Every module uses exactly these names:

```text
merchant_name
receipt_date
total_amount
invoice_id
merchant_address
```

Aliases such as `merchant`, `date`, `total` and `address` must not cross a module boundary.

## Value layers and ownership

| Layer | Owner | Meaning |
| --- | --- | --- |
| `raw_text` | OCR/KIE | Exact OCR source text used for the candidate |
| `predicted_value` | KIE | Selected business candidate before canonical normalization; string or `null` |
| `normalized_value` | KIE | Safely normalized typed value; string/date/integer or `null` |
| `corrected_value` | Backend/Human | Typed value explicitly supplied by a user; may be `null` when status is not `PRESENT` |
| `effective_value` | Backend | `corrected_value` when `has_correction=true`; otherwise `normalized_value` |

KIE never returns `corrected_value` or `effective_value`. Backend never rewrites KIE's `raw_text`, `predicted_value` or `normalized_value`.

`effective_value` never falls back to `predicted_value`. An unnormalized or ambiguous prediction is useful evidence, but it is not an effective business value.

## Value status

`value_status` and correction/effective statuses use:

| Status | Meaning | Value requirement |
| --- | --- | --- |
| `PRESENT` | Field exists and has a usable value | Typed value must be non-null |
| `NOT_PRESENT` | User/system confirms the field is absent from the receipt | Value must be `null` |
| `UNREADABLE` | Field region exists but cannot be read | Value must be `null` |
| `AMBIGUOUS` | Multiple plausible values remain | Normalized/effective value is `null` until corrected |
| `UNKNOWN` | No reliable conclusion | Value must be `null` |

Backend stores:

- machine `value_status` from KIE;
- nullable `corrected_status`;
- `has_correction` to distinguish no correction from an explicit null correction;
- derived `effective_status`.

An explicit `{ "value_status": "NOT_PRESENT", "value": null }` is a real correction. Clearing a correction is a separate DELETE operation and falls back to the machine result.

## OCR input and output

Worker invokes OCR with a Backend-generated `ocr_run_id`:

```json
{
  "receipt_id": "31915ef1-6fb4-4e7d-b6f5-53be51c50e3d",
  "ocr_run_id": "b3ac8bb4-6383-4b97-9911-5a6900054608",
  "image_path": "/private/tmp/31915ef1/receipt.jpg"
}
```

`image_path` is internal and is never exposed through the public API or persisted as the image identity.

OCR returns `examples/ocr-result.json`, conforming to `schemas/ocr-result.schema.json`.

Proposed OCR guarantees pending OCR Owner confirmation:

- `blocks` may be empty but is never `null`.
- `text` is trimmed Unicode and never an empty string.
- Every block has confidence in `[0,1]`.
- A polygon contains four normalized points, clockwise from the top-left region.
- `reading_order` is unique within one OCR run and zero-based.
- Engine-specific objects do not cross the adapter boundary.

## KIE input and output

KIE receives one complete OCR result unchanged and returns `examples/kie-result.json`, conforming to `schemas/kie-result.schema.json`.

Run linkage is mandatory:

```text
KIEResult.source_ocr_run_id == OCRResult.ocr_run_id
```

KIE guarantees:

- All five canonical field keys are always present.
- `raw_text` preserves source OCR text.
- `predicted_value` is the selected, unnormalized candidate string.
- `normalized_value` is populated only when a tested normalization rule succeeds.
- Non-`PRESENT` statuses have `normalized_value=null` and `machine_needs_review=true`.
- `source_block_ids` contains only IDs from the referenced OCR run.
- `invoice_id` remains a string so leading zeroes are preserved.
- `total_amount.normalized_value` is an integer VND when safely normalized.
- Field confidence describes confidence in the business prediction, not only OCR confidence.

## Ambiguous normalization

KIE must not silently change letters to digits without a tested rule. For example, OCR text `325.OOO VND` must not automatically become `325000` merely by replacing `O` with `0`.

Until such a rule is tested, return:

```json
{
  "raw_text": "325.OOO VND",
  "predicted_value": "325.OOO VND",
  "normalized_value": null,
  "currency": "VND",
  "value_status": "AMBIGUOUS",
  "confidence": 0.4,
  "machine_needs_review": true,
  "review_reasons": ["AMBIGUOUS", "NORMALIZATION_FAILED"],
  "source_block_ids": ["block_5"]
}
```

The main valid example uses unambiguous `325.000 VND`.

## Immutable processing runs

- Every processing attempt creates a new `ocr_run_id` and, if OCR succeeds, a new `kie_run_id`.
- `KIEResult.source_ocr_run_id` points to the exact OCR run it consumed.
- OCR blocks and KIE predictions are append-only by run; reprocessing never overwrites prior machine output.
- Receipt detail may expose the latest run by default, while run IDs preserve traceability.
- Correction history records the field/run context that the user reviewed.

## Human correction semantics

Apply a correction:

```json
{
  "value": null,
  "value_status": "NOT_PRESENT",
  "expected_updated_at": "2026-08-10T08:30:00Z"
}
```

This means the user confirmed that the field does not exist. It does not clear the correction.

Clear the correction and fall back to the KIE result:

```text
DELETE /api/v1/fields/{field_id}/correction
```

Correction history stores both value and status transitions: `old_value`, `new_value`, `old_status`, `new_status`.

## Machine and effective review flags

KIE returns immutable `machine_needs_review`. It describes the machine result at the time of the KIE run and is true for unresolved `NOT_PRESENT`, `UNREADABLE`, `AMBIGUOUS`, `UNKNOWN`, normalization failure or format failure. Human actions never overwrite this historical flag.

Backend returns `effective_needs_review`, which describes the field's current review state:

1. It is `false` when the field or receipt has been verified.
2. When `has_correction=true`, it is `false` for a resolved correction status (`PRESENT`, `NOT_PRESENT` or `UNREADABLE`) and `true` for `AMBIGUOUS` or `UNKNOWN`.
3. Otherwise it equals `machine_needs_review`.

Frontend uses `effective_needs_review` for current warning indicators. It may show `machine_needs_review` only as provenance/history.

Confidence thresholds `0.60` and `0.85` are **provisional configuration only**. They have not been calibrated on VietReceipt evaluation data and are not acceptance criteria for contract v1.3. The thresholds must remain configurable/TBD until measured on a validation set.

## Example-data disclaimer

Values in `examples/` illustrate contract shape and linkage only. Confidence values, durations, engine/extractor names and versions, UUIDs, run IDs and block IDs are not benchmark results, production defaults, performance claims or evaluation evidence.

## Ground-truth annotation contract

Human dataset annotations use `docs/field-specification.md`, `schemas/annotation-record.schema.json` and `examples/annotation-record.example.json`.

This is intentionally separate from KIE runtime output:

| Ground truth | KIE runtime | Reason |
| --- | --- | --- |
| `annotation_status` | `value_status` | Same vocabulary, different owner and provenance |
| `transcribed_value` | `raw_text` | Human transcription is not OCR/KIE text |
| `normalized_value` | `normalized_value` | Same canonical type, but ground truth versus prediction |
| `candidate_values` | No direct field | Annotation alternatives are evaluation evidence, not a selected prediction |
| No confidence/review flag | `confidence`, `machine_needs_review` | Ground truth must not claim machine confidence |

Both contracts use the same five canonical field names and typed normalized values. Annotation `source_block_ids` must refer to blocks in its exact `source_ocr_run_id`.

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

- `code` is stable and machine-readable.
- `message` is safe for users.
- `details` is optional and contains no secret or stack trace.
- Every API response includes `X-Request-ID`; errors repeat it in the body.

## Versioning rule

- Compatible additions require a minor revision and remain optional.
- Removing/renaming a field, changing a type or coordinate semantics requires a new major version after v1 is finalized.
- Contract changes update schemas, examples, OpenAPI and consumer tests in one Pull Request.
