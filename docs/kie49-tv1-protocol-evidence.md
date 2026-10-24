# TV4 protocol evidence for TV1/TV2 follow-up

**Date:** 2026-10-24  
**Scope:** development-only metric and matcher evidence; not dataset QA, benchmark
accuracy, final-test authorization, or human sign-off.  
**Compared inputs:** TV1 PR #64 at `1b63cb88528ad431c88436d3c500c913f7fd23e5`
and TV2 PR #66 at `89281198ebaf419e511b4c99321ca3355e94fcf1`.

## TV4 response to D1: exact-value extraction

TV4 accepts the proposed D1 definitions. The evaluator now emits explicit
`true_positive`, `false_positive`, and `false_negative` counts for every header,
plus micro exact-value extraction precision/recall/F1 under
`exact-value-extraction-1.0`. A wrong PRESENT value contributes one FP and one FN.
A PRESENT prediction against known non-PRESENT gold contributes one FP. Gold
UNKNOWN remains outside the corresponding accuracy denominator.

The report also exposes all five gold status counts per field and in aggregate,
and prediction status counts on known gold. UNREADABLE and AMBIGUOUS remain known
status labels for exact status+value comparison, but never become recovered
PRESENT values. Failed eligible documents remain in processing and strict
document denominators; each labeled PRESENT header becomes an FN. Zero
denominators remain JSON `null`.

This change adds audit counters to the existing `invoice-evaluation-2.2.0`
semantics. It does not rename historical result files or recalculate a previous
run. The implementation commit hash and `implementation_sha256` still identify
the exact scorer used by each future report.

The synthetic regression `test_header_exact_value_protocol_matrix` covers TV1
M01-M09: correct value, wrong value, missing value, false PRESENT, correct
NOT_PRESENT, UNKNOWN masking, UNREADABLE/AMBIGUOUS, strict unscoreability, and a
processing failure.

## TV4 response to D2: source row matcher

TV4 keeps `page-bbox-positive-iou-cardinality-1.0` as a **development
candidate**. No threshold has been tuned from the pending dataset or a held-out
set. The cases below use synthetic coordinates chosen before any scored final
run. Counts are row-detection TP/FP/FN.

| Case | Predicted bounds | Gold bounds | Observed match/counts | Interpretation |
| --- | --- | --- | --- | --- |
| Edge touch | `[.10,.20,.50,.30]` | `[.50,.20,.90,.30]` | none; 0/1/1 | Zero-area contact is rejected. |
| Tiny positive overlap | `[.10,.20,.50,.30]` | `[.499999,.20,.90,.30]` | `(0,0)`; 1/0/0 | Candidate accepts any positive area. This is a known false-match risk requiring human review. |
| Neighboring rows | two disjoint y ranges `.20-.25`, `.30-.35` | same two ranges | two; 2/0/0 | Separate rows remain separate. |
| Merged prediction | one box `.20-.40` | two boxes `.20-.29`, `.31-.40` | one; 1/0/1 | One-to-one cardinality prevents one prediction claiming both rows. |
| Split predictions | two boxes `.20-.29`, `.31-.40` | one box `.20-.40` | one; 1/1/0 | One split fragment matches; the other is an FP. |
| Multiple optima | two identical predictions | two identical gold boxes | stable pairs `(0,1),(1,0)`; 2/0/0 | Repeated runs are deterministic. |
| Page mismatch | page 0 prediction | identical page 1 gold | none; 0/1/1 | Matching is page-aware. |
| Displaced frame | `[.60,.60,.90,.70]` | `[.10,.20,.50,.30]` | none; 0/1/1 | Matching does not infer rotation/crop transforms. |

The tests also preserve the value-blind rule: changing normalized cell values or
sharing OCR IDs cannot increase a source-region match. Empty/empty row sets keep
precision, recall and F1 null while explicit empty-table strict correctness is
handled separately.

EXIF and PDF geometry are validated upstream by the merged TV5 original-file
runner. `test_exif_display_coordinate_frame` verifies image dimensions after
EXIF transpose; `test_rotated_pdf_uses_canonical_unrotated_media_frame` verifies
the cropped, unrotated PDF frame. The runner rejects an unreviewed coordinate
profile or page mismatch rather than guessing a transform. TV4 therefore accepts
the current matcher only for further development review. Final freeze remains
blocked until TV1 and TV2 review the tiny-overlap limitation and explicitly
accept this version or register a new development-only threshold/version.

## TV2 intake v2 verification

The TV2 overlay archive from PR #66 was checked independently:

- archive SHA-256 is
  `fca8aa088b54da280dbca776b7d654c339c0d3717fb368b4a96ace2140cce223`;
- all 84 files declared by the package manifest match their individual hashes;
  the archive has one additional README;
- all 80 review receipts have no named reviewer/date and all five approval flags
  are `false`;
- the unchanged v1 artifacts replay through both groupers for 80/80 records with
  no contract failures;
- `eligible_for_accuracy=0`, `qa_status=PENDING_REVIEW`, and `metrics=null`;
- train 60 and validation 20 scored evaluator calls both exit 2. On current
  `main`, the first reported gate is missing typed verification provenance,
  consistent with blank `verified_by` and the pending manifest state.

No baseline/variant accuracy comparison can be published from this intake. A
reviewed release still needs actual annotator/reviewer identities, timezone-aware
review dates, five approvals per sample, owner sign-off, and all typed/frozen
manifest provenance required by the evaluator.

Local verification passed 140 targeted KIE tests, 186 tests under full unittest
discovery, 24 source-runner tests, and the shared JSON/OpenAPI/linkage contract
suite. Python import/format checks also pass for the changed implementation and
tests.

## TV4 co-sign position

TV4 can co-sign D1 with the tested contract above. TV4 can only co-sign D2 as a
development candidate with the tiny-positive-overlap limitation recorded. TV4
does not authorize final freeze, a superiority claim, closing #47/#49, or opening
the final dataset while independent review remains 0/80.

Suggested PR #64 review text after a human reviewer verifies this commit:

> TV4 APPROVE D1 against `invoice-evaluation-2.2.0` plus
> `exact-value-extraction-1.0`: M01-M09 pass and explicit per-field/micro TP/FP/FN
> are emitted. TV4 accepts `page-bbox-positive-iou-cardinality-1.0` only as a
> DEVELOPMENT CANDIDATE: R01-R07 and canonical EXIF/PDF frame regressions pass,
> while tiny positive overlap remains a documented false-match risk. TV2 intake
> v2 passes integrity and 80/80 unscored replay, but independent review is 0/80,
> so metrics remain null and final freeze remains blocked.
