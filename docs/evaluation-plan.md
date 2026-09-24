# Evaluation Plan v3

## Principle

The final thesis/demo must be judged primarily by **end-to-end invoice correctness on frozen held-out data**.

Module-level OCR/KIE scores are diagnostic. They are not a substitute for end-to-end performance.

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

### 4. End-to-end invoice completion

Report:

- complete-header accuracy: all required evaluated header fields correct;
- complete-invoice accuracy: all required header fields + required evaluated line-item structure correct;
- field-correction count needed to reach confirmed output;
- failure stage for documents that do not reach reviewable structured output.

This is the primary headline evaluation layer.

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
