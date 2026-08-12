# Shared ground-truth annotation contract v1.0

This document defines the shared record envelope, data types and machine-validation rules for five-field ground-truth annotations. It does not redefine field meaning, inclusion/exclusion policy or normalization decisions owned by KIE.

## Normative ownership

| Concern | Source of truth | Owner |
| --- | --- | --- |
| Field meaning, inclusion/exclusion and normalization | `ai/kie/docs/field-specification.md` | KIE |
| Annotator decision process and edge cases | `ai/kie/docs/annotation-guidelines.md` v1.1 | KIE |
| Shared envelope, canonical data types and validation | This document and `schemas/annotation-record.schema.json` | KIE + Backend/Data |

When a KIE rule changes, the KIE documents are changed first and the shared schema/example/tests must be updated in the same Pull Request when affected. This document must link to KIE-owned semantics rather than copying them into a second field specification.

The machine-readable schema is `schemas/annotation-record.schema.json`; the linked synthetic example is `examples/annotation-record.example.json`.

## Record envelope and provenance

| Property | Type | Required | Meaning |
| --- | --- | --- | --- |
| `record_type` | string constant | Yes | `five-field-ground-truth-annotation` |
| `annotation_schema_version` | string constant | Yes | Shared schema version; `1.0` |
| `guideline_version` | string constant | Yes | KIE guideline version; `1.1` |
| `annotation_id` | UUID | Yes | Unique identity of this annotation/adjudication record |
| `batch_id` | non-empty string | Yes | Annotation batch identity |
| `dataset_snapshot` | non-empty string | Yes | Immutable dataset snapshot identity |
| `example_only` | boolean | Yes | `true` only for synthetic documentation examples |
| `data_provenance` | non-empty string | Yes | Origin and permitted interpretation of the record |
| `receipt_id` | UUID | Yes | Receipt being annotated |
| `source_ocr_run_id` | UUID | Yes | Exact OCR run whose blocks may be referenced |
| `annotator_id` | non-empty string | Yes | Stable annotator/adjudicator identity |
| `annotated_at` | RFC 3339 timestamp or `null` | Yes | May be `null` only when `example_only=true` |
| `fields` | object | Yes | Exactly the five canonical field annotations |

An actual record must set `example_only=false` and supply a non-null `annotated_at`. Multiple annotations of the same receipt remain distinguishable through `annotation_id`, `annotator_id`, `batch_id`, `dataset_snapshot` and guideline version.

## Canonical field keys and types

The `fields` object contains exactly the following keys. `field_name` inside each annotation must equal its containing key.

| Field | Canonical `normalized_value` and candidate type |
| --- | --- |
| `merchant_name` | non-empty string |
| `receipt_date` | ISO date `YYYY-MM-DD` |
| `total_amount` | non-negative integer VND; `currency="VND"` |
| `invoice_id` | non-empty string; leading zeroes preserved |
| `merchant_address` | non-empty string |

Aliases such as `merchant`, `date`, `total` and `address` are rejected.

## Annotation object

Each field annotation contains:

| Property | Meaning |
| --- | --- |
| `field_name` | Canonical name matching its containing key |
| `annotation_status` | `PRESENT`, `NOT_PRESENT`, `UNREADABLE`, `AMBIGUOUS` or `UNKNOWN` |
| `transcribed_value` | Exact human transcription from the receipt image, or `null` |
| `normalized_value` | Human-validated canonical value, or `null` |
| `source_block_ids` | Unique OCR block IDs from `source_ocr_run_id` |
| `candidate_values` | Canonically typed alternatives for an ambiguous annotation |
| `annotator_note` | Explanation required by the rules below, otherwise optional |

## OCR omission rule from KIE guideline v1.1

No extra evidence enum is added to the shared record. A normal `PRESENT` annotation has at least one `source_block_id`. When the annotator can read the field directly from the receipt image but the referenced OCR run produced no usable block, KIE guideline v1.1 represents the exception as:

```json
{
  "annotation_status": "PRESENT",
  "source_block_ids": [],
  "annotator_note": "OCR_OMISSION"
}
```

The schema accepts an optional explanation after the code, for example `OCR_OMISSION: value read directly from image`, but the note must start with `OCR_OMISSION`. A note carrying this code is valid only for `PRESENT` with an empty block list.

## Annotation-status invariants

| Status | Enforced rules |
| --- | --- |
| `PRESENT` | Non-null transcription and correctly typed normalized value; candidates empty; at least one source block, or empty blocks with note starting `OCR_OMISSION` |
| `NOT_PRESENT` | Both values `null`; source blocks and candidates empty |
| `UNREADABLE` | Normalized value `null`; candidates empty; non-empty note; source blocks may be present |
| `AMBIGUOUS` | Normalized value `null`; at least one typed candidate and a non-empty explanatory note |
| `UNKNOWN` | Both values `null`; source blocks and candidates empty; non-empty note |

Empty strings are never substitutes for `null`.

## Separation from runtime contracts

Ground truth is not KIE output and not a Backend correction:

| Ground truth | KIE runtime | Difference |
| --- | --- | --- |
| `annotation_status` | `value_status` | Same vocabulary, different owner/provenance |
| `transcribed_value` | `raw_text` | Human reading from the image versus OCR/KIE source text |
| `normalized_value` | `normalized_value` | Ground truth versus machine prediction |
| `candidate_values` | No direct equivalent | Annotation alternatives are evaluation evidence |
| No confidence/review flag | `confidence`, `machine_needs_review` | Ground truth does not claim machine confidence |

Backend corrections remain operational audit records and do not overwrite either ground truth or immutable KIE results.

## Cross-record validation

JSON Schema validates one record's shape. `scripts/validate_annotation_ocr.py` additionally enforces:

```text
annotation.receipt_id == ocr.receipt_id
annotation.source_ocr_run_id == ocr.ocr_run_id
every annotation source_block_id exists in ocr.blocks
```

Run all positive, negative and linkage checks with:

```bash
python3 tests/contracts/run_contract_tests.py
```
