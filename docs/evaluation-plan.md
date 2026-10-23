# Evaluation Plan v4

## Principle

The final thesis/demo must be judged primarily by **end-to-end invoice correctness on frozen held-out data**.

Module-level OCR/KIE scores are diagnostic. They are not a substitute for end-to-end performance.

The canonical protocol and metric formulas are in [evaluation-matrix.md](evaluation-matrix.md). The study design is in [research-design.md](research-design.md); the optional human pilot is gated by [user-study-protocol.md](user-study-protocol.md). These are proposed rules until TV2, TV4 and TV5 record approval in the matrix.

## Evaluation layers

### 1. OCR / text reading

Report OCR/text-reading quality separately from KIE.

Use CER/WER where reference transcription exists and record evidence failures that affect downstream extraction.

For born-digital PDF experiments, also record direct-text extraction success/failure and whether fallback OCR was needed.

### 2. Header-field extraction

For every supported canonical field report:

- exact normalized-value accuracy or exact match;
- precision / recall / F1 where appropriate;
- misses;
- wrong values;
- false values when the source does not contain the field;
- unresolved/ambiguous cases;
- review rate.

Do not hide weak fields behind one aggregate.

### 3. Structured line items

Report at least:

- line detection recall;
- extra-row rate;
- matched-line cell correctness;
- per-column correctness for description, unit, quantity, unit price and amount;
- complete-line accuracy: all required cells in a matched row correct;
- complete-table accuracy when sample size permits.

A flat set/list of predicted values is not a successful line-item result unless values are linked into rows.

For a method comparison, use the current row-producing geometry baseline versus one proposed row-producing variant on identical OCR evidence. A flat, ungrouped list has no valid row detection or complete-line score. Do not claim a row-grouping gain from comparing a scoreable structured result with an undefined flat-row denominator.

### 4. End-to-end invoice completion

Report:

- complete-header accuracy: all required evaluated header fields correct;
- complete-invoice accuracy: all required header fields + required evaluated line-item structure correct;
- field-correction count needed to reach confirmed output;
- failure stage for documents that do not reach reviewable structured output.

This is the primary headline evaluation layer.

Use the explicit scope **13 supported headers + line items; tax groups excluded** until tax gold is added through a versioned annotation contract. Every in-scope file that fails before structured output stays in the eligible processing denominator and scores as a failed document. A document with UNKNOWN in a required source-gold cell remains in processing counts but is not scoreable for strict complete-invoice accuracy; report both counts.

### 5. Generalization

Report separately:

- seen-template validation;
- unseen-template final test;
- independent mock final test.

Do not pool seen and unseen layouts into one score and call it generalization.

### 6. Robustness

When controlled variants exist, report the same end-to-end metrics for:

- clean;
- blur/noise;
- rotated/perspective;
- scan-like/compressed.

If severity levels are generated, show degradation curves rather than only the easiest and hardest cases.

### 7. System behavior

Measure:

- upload-to-result processing time;
- stage latency when available;
- failure rate by processing stage;
- export/schema validity;
- fallback rate from direct PDF extraction to OCR.

## Required baseline and ablation experiments

### E1 — OCR-all vs route-aware reading

**B0 OCR-all:** rasterize every eligible PDF/image and run OCR.

**P1 Route-aware:** direct text/position extraction for usable text PDFs; OCR only for image/scan content.

Compare on the same born-digital PDF subset:
- end-to-end header accuracy;
- line-item accuracy when supported;
- processing latency;
- failure rate.

### E2 — Structured line-item grouping

Compare:
- flat extraction / no row grouping;
- final row-grouped line-item extraction.

The purpose is not to claim the flat output is useful; it is to quantify the contribution of row reconstruction.

### E3 — Normalization and consistency checks

Compare final field correctness before and after deterministic normalization/checks where both outputs are meaningful.

Do not count user corrections as machine accuracy.

### E4 — Seen vs unseen template

Use the template-disjoint split from `docs/dataset-strategy.md`.

This is mandatory for any claim about layout generalization.

## User pilot

Optional but valuable when participants are available.

A valid pilot should use comparable tasks:
- manual entry/review;
- VietReceipt-assisted review.

Measure:
- direct completion time;
- final correctness;
- number of corrections;
- optional short usability rating.

With 2–4 participants, report descriptive results only. Do not claim population-level effects.

## Dataset reporting

Every result table must name:

- dataset family;
- exact snapshot/version;
- split/manifest;
- sample count;
- synthetic/public/mock/real flag;
- template seen/unseen status;
- configuration;
- git commit.
- eligible input count, failed count, source-gold scoreable count and UNKNOWN annotation coverage;
- whether metrics come from immutable machine output or a separate human-reviewed output.

CORD/SROIE results are external benchmark results, not evidence of Vietnamese enterprise performance.

## Frozen test rule

Final test manifests are frozen before final tuning. If a test result is inspected and then used to change the algorithm, that test is no longer an untouched final test for the changed version.

The independent mock test and unseen-template final test should only be opened after:
- extraction logic/configuration is frozen;
- thresholds are frozen;
- report metric definitions are frozen.

## Error analysis

Every final benchmark should produce an error taxonomy, including at least:

- source-routing failure;
- OCR omission/substitution;
- reading-order/geometry failure;
- field candidate failure;
- field ranking/classification failure;
- normalization failure;
- line grouping failure;
- arithmetic/consistency failure;
- annotation/mapping issue;
- unsupported/out-of-scope layout.

Include representative examples and counts. Do not describe only successful samples.

## Web demo

The web demo proves functional integration:

upload → processing → review → correction → confirmation → export.

Do not claim accountant time savings unless a real manual-vs-tool study is separately designed and executed. A synthetic dry run is not a user study.

## Executable TV4 V2 evaluator

`python scripts/evaluate_invoice_kie.py --manifest <authorized-frozen-manifest>`
implements per-header metrics, evidence-based one-to-one row matching, line recall,
extra rows, matched cells/per-column correctness, complete-line/table/header/invoice
accuracy and automatic error diagnostics. Optional verified oracle evidence enables
paired OCR-propagation diagnostics. Manifest/artifact hashes, dataset/split/template
regime, synthetic flag, code/config versions and git/content provenance are recorded.

The default missing-data state is `WAITING_FOR_VERIFIED_V2_GOLD`, exit 2,
zero evaluated samples and null metrics/modes/gap. Unit fixtures cannot stand in for
frozen TV2 gold. Exact eligibility checks, denominator definitions, oracle limitations
and manifest format are documented in [the V2 guide](kie-v2.md#evaluation-protocol).
This is a module evaluator; full source-routing failures, latency, unseen-template
experiments and actual upload-to-export acceptance remain part of the wider plan.

### Current implementation gaps — do not report as final metrics

- `scripts/evaluate_invoice_kie.py` evaluates KIE against OCR evidence, not original uploaded bytes. `scripts/evaluate_backend_v2.py` runs the source-file HTTP workflow and records machine snapshots/timing/failures, but does not score source-gold accuracy.
- Annotation-v2 has no independent source-region gold or tax-group gold. OCR-aligned gold must not be presented as an end-to-end source benchmark.
- The current evaluator accepts `UNKNOWN` labels but its metric aggregation treats every non-PRESENT gold status as a negative for presence and includes them in exact-match denominators. This differs from the protocol in [evaluation-matrix.md](evaluation-matrix.md). Until evaluator code and regression tests are updated, do not score manifests containing UNKNOWN labels or call their metrics final.
- `complete_invoice_accuracy` currently covers all 13 header cells and row/table output only. It does not include tax groups. Keep that scope in every report.
