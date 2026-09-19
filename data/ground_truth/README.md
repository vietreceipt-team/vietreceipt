> **LEGACY v1 NOTICE (19/09/2026):** This file belongs to the former five-field Week-1/2/3 plan. Do not use it as a current requirement. See `README.md`, `docs/project-plan.md` and `docs/migration-status.md`.

# Ground-truth transcription policy

This probe currently contains 40 non-empty first-pass transcriptions, covering
`R001` through `R040`. Empty placeholder files are not valid annotations and
must not be created.

## Status and QA

- `not_started`: no transcription file exists.
- `annotated`: a non-empty first-pass transcription exists.
- `reviewed`: a second person checked the transcription against the authorized
  source image and accepted it.

The original seven transcriptions (`R001`, `R002`, `R006`, `R019`, `R021`,
`R023`, and `R028`) predate explicit tracking and retain
`annotator_id=unknown_legacy_contributor`. The 33 transcriptions added in commit
`73c55f0` use `annotator_id=unknown_contributor` because repository history does
not identify the person who performed the transcription. All 40 remain
`qa_status=pending_review` and must not be promoted to `reviewed` until a named,
independent reviewer checks them. Per-sample provenance is in
`annotation_metadata.csv`, and `data/test_set/test_manifest.csv` is the source
of truth for evaluation status.

## Transcription rules

1. Preserve Unicode text, diacritics, punctuation, visible line order, and
   meaningful line breaks.
2. Do not silently correct spelling, totals, dates, or invoice identifiers.
3. Collapse of whitespace is an evaluation-only normalization; source files
   retain the human transcription.
4. Do not guess unreadable text. Record the ambiguity during annotation review
   instead of inventing content.
5. A second reviewer must be different from the annotator before the status can
   become `reviewed`.

The MC-OCR source license does not grant repository redistribution. These
transcriptions are retained only as the pre-existing internal research probe and
must not be treated as a redistributable dataset release.
