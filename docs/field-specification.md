# Five-field ground-truth annotation specification v1.0

This specification defines human ground-truth annotations for the five canonical VietReceipt fields. It is a dataset/evaluation contract, not a KIE runtime result and not a Backend correction record.

The machine-readable schema is `schemas/annotation-record.schema.json`. A synthetic record is available at `examples/annotation-record.example.json`.

## Record envelope

| Property | Type | Required | Meaning |
| --- | --- | --- | --- |
| `record_type` | string constant | Yes | Always `five-field-ground-truth-annotation` |
| `annotation_schema_version` | string constant | Yes | Always `1.0` for this schema |
| `guideline_version` | non-empty string | Yes | Annotation guideline used by the annotator |
| `example_only` | boolean | Yes | `true` only for synthetic documentation examples |
| `data_provenance` | non-empty string | Yes | Origin and permitted interpretation of the record |
| `receipt_id` | UUID string | Yes | Receipt being annotated |
| `source_ocr_run_id` | UUID string | Yes | Exact OCR run whose blocks are referenced |
| `annotator_id` | non-empty string | Yes | Stable annotator or adjudicator identifier |
| `annotated_at` | RFC 3339 timestamp or `null` | Yes | May be `null` only for an example record |
| `fields` | object | Yes | Exactly the five canonical field annotations |

An actual dataset record must set `example_only=false` and supply a non-null `annotated_at` timestamp. Example records may use synthetic UUIDs and a null timestamp.

## Canonical field keys

The `fields` object contains exactly:

```text
merchant_name
receipt_date
total_amount
invoice_id
merchant_address
```

For every entry, `field_name` must equal its containing key. Aliases such as `merchant`, `date`, `total` or `address` are rejected.

## Annotation object

| Property | Type | Meaning |
| --- | --- | --- |
| `field_name` | canonical field name | Repeats the containing key for standalone processing and validation |
| `annotation_status` | enum | `PRESENT`, `NOT_PRESENT`, `UNREADABLE`, `AMBIGUOUS` or `UNKNOWN` |
| `transcribed_value` | string or `null` | Exact human transcription of visible receipt text; not OCR output |
| `normalized_value` | canonical typed value or `null` | Human-validated normalized ground truth |
| `source_block_ids` | array of unique strings | OCR blocks from `source_ocr_run_id` supporting the annotation |
| `candidate_values` | array | Plausible normalized alternatives, mainly for ambiguous annotations |
| `annotator_note` | string or `null` | Optional rationale, uncertainty or normalization note |

`total_amount` additionally requires `currency="VND"`.

## Canonical value types

| Field | `normalized_value` and candidate type |
| --- | --- |
| `merchant_name` | string |
| `receipt_date` | ISO date string `YYYY-MM-DD` |
| `total_amount` | non-negative integer VND |
| `invoice_id` | string; leading zeroes are preserved |
| `merchant_address` | string |

## Status rules

- `PRESENT`: `transcribed_value` and `normalized_value` are non-null, and `source_block_ids` contains at least one block.
- `NOT_PRESENT`: both values are `null`; source blocks and candidates may be empty.
- `UNREADABLE`: `normalized_value` is `null`; `transcribed_value` may contain a partial transcription or be `null`.
- `AMBIGUOUS`: `normalized_value` is `null`; `candidate_values` may list plausible canonical alternatives.
- `UNKNOWN`: `normalized_value` is `null` because no reliable conclusion is available.

For every non-`PRESENT` status, `normalized_value` must be `null`. Empty strings are not substitutes for missing values.

## Ownership and mapping

- The annotation team owns this ground-truth record.
- OCR owns the referenced blocks and never receives annotation fields as OCR output.
- KIE may consume annotations for training/evaluation, but its runtime output remains `KIEResult` with `raw_text`, `predicted_value`, `normalized_value`, confidence and `machine_needs_review`.
- Backend human corrections remain operational audit records and do not overwrite dataset ground truth.
- `annotation_status` has the same vocabulary as KIE `value_status`, but the two properties have different owners and provenance.

## Cross-record validation

JSON Schema validates shape and value types. Dataset tooling must additionally verify:

```text
AnnotationRecord.source_ocr_run_id == OCRResult.ocr_run_id
```

and every annotation `source_block_ids[]` value exists in that OCR result.
