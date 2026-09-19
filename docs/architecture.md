# VietReceipt Architecture v2

## System goal

A web application receives an invoice document, produces structured invoice data, lets a user review/correct it and exports the confirmed result.

## Logical flow

```text
Browser
  │
  │ REST/JSON + multipart upload
  ▼
FastAPI
  ├─ receipt metadata / status
  ├─ review corrections
  ├─ confirmation
  └─ export
  │
  ▼
Processing scheduler / worker
  ├─ source classifier
  ├─ PDF text extractor
  ├─ image preprocessing
  ├─ OCR adapter
  ├─ KIE / line-item extraction
  ├─ normalization
  └─ consistency checks
  │
  ├──────────────► object storage (source files)
  └──────────────► PostgreSQL (metadata, runs, extracted data, corrections)
```

Redis/Celery may remain the first queue implementation. Queue state is not the source of truth.

## Processing paths

### Image / digitized paper

image → preprocessing when justified → OCR → OCR blocks/geometry → KIE

### PDF with usable text layer

PDF → direct text/position extraction → canonical text blocks → KIE

### PDF scan/image-only

PDF pages → images → OCR → KIE

All paths must converge on the same KIE contract.

## Immutable runs

Each processing attempt creates new OCR/KIE run IDs. Previous machine results are preserved. Human corrections are stored separately from machine output.

## Review workflow

Public lifecycle remains:

- UPLOADED
- PROCESSING
- NEEDS_REVIEW
- VERIFIED
- FAILED

A field can be PRESENT, NOT_PRESENT, UNREADABLE, AMBIGUOUS or UNKNOWN.

Machine confidence is evidence, not a verified probability of correctness. The UI must not hide uncertain fields merely because a threshold is high.

## Canonical content

Header fields are defined in `docs/integration-contracts.md`. Tax breakdown and line items are first-class structured outputs, not text pasted into a single field.

## Security/data handling

- never commit private invoice documents or credentials;
- dataset provenance and license/access conditions must be recorded;
- source files and exported results should be isolated from public demo fixtures;
- synthetic fixtures are preferred for screenshots, CI and public demos.
