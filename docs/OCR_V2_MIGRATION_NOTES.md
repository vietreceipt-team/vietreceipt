# TV3 migration audit — Issue #48

Base: `origin/main` at `4f662e9`, invoice V2 roadmap. Audited `ai/ocr/`,
`schemas/ocr-result.schema.json`, `docs/migration-status.md`, integration contracts,
and TV5/TV6 provider interfaces from PRs #53/#54.

| Decision | Component | Reason |
|---|---|---|
| KEEP | PaddleOCR 3.0.3 / PaddlePaddle 3.0.0 / PaddleX 3.0.3, Vietnamese PP-OCRv3 | Reuse pinned working CPU baseline |
| KEEP | `ai/ocr/pipeline.py`, geometry validation, UUID inputs | Semantic-field-agnostic inference already exists |
| KEEP | Legacy OCRResult 1.3 and existing tests | TV5 validates individual pages against this schema |
| KEEP | Legacy immutable artifact utilities | Existing callers retain their behavior |
| CHANGE | OCR engine factory gets optional textline orientation parameter | V2 owns document orientation; legacy default stays unchanged |
| ADD | `ai/document_reader/` | PDF routing, text extraction, rendering, orientation, multi-page envelope |
| ADD | `document-evidence.v2.schema.json` and cross-page validator | Formalize envelope already accepted by TV5/TV6 |
| ADD | Worker error adapter, benchmark, fixture generator, source overlay demo, CI | Make module callable, reproducible and reviewable |
| REMOVE from V2 dependencies | `field_analysis.py`, five-field evaluation/annotation assumptions | Those legacy utilities remain on disk but are not imported by the reader |

## Contracts

The main OCR schema is single-page. TV5 #53 already accepts `document-2.0` with
`pages: [{page_index, evidence: OCRResult1.3}]`; TV6 #54 understands that same shape.
The new reader always emits this envelope, including one-page images. Block IDs
are unique across the document (`p0_b000000`), reading order resets per page and
is contiguous. Receipt/run IDs are supplied by the caller, never benchmark IDs.

PDF coordinates use the unrotated cropped page, matching TV6's explicit PDF.js
`getViewport({rotation: 0})`. Image coordinates use the EXIF-transposed source as
displayed by browsers. OCR performed after orientation correction is mapped back
to that source. Downstream consumers must not sort transformed blocks again.

## Compatibility decision requiring awareness

OCRResult 1.3 requires numeric confidence. Direct PDF extraction has no OCR
probability. For compatibility it uses numeric **sentinel 1**, identified by
`engine.name = pdfium-text`; metadata explicitly says
`not_applicable_legacy_sentinel_1`. KIE/UI must treat this as N/A, not 100% OCR or
field confidence. Changing confidence to nullable would require coordinated
TV4/TV5/TV6 schema migration, so this PR does not silently change their contract.

## Ownership

TV3 returns text/geometry, not header/line-item semantics. TV2 owns dataset splits
and verified ground truth. TV4 supplies KIE V2; TV5 owns worker/DB/retry; TV6 owns
the product viewer. Module and provider-contract verification are not proof of
the complete deployed upload → KIE → review → export workflow.
