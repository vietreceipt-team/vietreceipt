# TV1 — Results, ablation and error-analysis workbook (fillable template)

**Status (26 October 2026):** No independent final source-gold metrics have been verified. Empty table cells below are deliberate. The development statistics from PR descriptions are separated from scored accuracy. Read with [evaluation matrix](evaluation-matrix.md), [TV1 decisions](tv1-evaluation-decisions.md), and [thesis draft](tv1-thesis-manuscript.md).

## 1. Required evidence header for every table

| Item | Value |
|---|---|
| Experiment ID and date | NOT RUN |
| Dataset, licensing/provenance and version | NOT RECORDED |
| Original source manifest SHA-256; gold/regions SHA-256 | NOT RECORDED |
| Split, independent families, base documents, derived variants | NOT RECORDED |
| Reader/KIE/backend/evaluator version and code SHA | NOT RECORDED |
| Runtime fingerprint, cold/warm condition, model versions | NOT RECORDED |
| Gold reviewer / adjudication record | PENDING |
| Count of eligible, scoreable, failed, gold UNKNOWN | NOT MEASURED |
| Prediction artifact hashes and output location | NOT RECORDED |

Never fill a metric with zero where the run or denominator is unavailable: write **N/A — not scored**, and give the reason. No post-review correction appears in machine-only scores.

## 2. Source-file end-to-end outcomes (E1/E4/E5/E6)

| Dataset & split | Route | Template regime | Quality slice | Eligible N | Scoreable N | Failed N | Header exact | Complete-line | Complete-table | Complete-invoice (13+rows; tax excluded) | p50/p95 terminal wall time | Artifact |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Independent mock (planned) | JPG/PNG | unseen | clean | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | NOT RUN |
| Independent mock (planned) | text PDF | unseen | clean | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | NOT RUN |
| Independent mock (planned) | scan PDF | unseen | clean | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | NOT RUN |

**Accuracy denominator:** complete-invoice N = scoreable originals with all required known gold labels, including machine failures among those originals. Overall processing rate uses all *eligible* originals. Variants are paired under their base identity; do not count them as independent invoices.

## 3. Per-header value-aware diagnostics

Repeat this table for each dataset/route/family slice; include all 13 fields.

| Header field | Known gold | UNKNOWN | TP | FP | FN | Exact match numerator / denominator | P | R | F1 |
|---|---|---|---|---|---|---|---|---|---|
| invoice_template_number | — | — | — | — | — | — | — | — | — |
| invoice_symbol | — | — | — | — | — | — | — | — | — |
| invoice_number | — | — | — | — | — | — | — | — | — |
| invoice_date | — | — | — | — | — | — | — | — | — |
| seller_name | — | — | — | — | — | — | — | — | — |
| seller_tax_id | — | — | — | — | — | — | — | — | — |
| seller_address | — | — | — | — | — | — | — | — | — |
| buyer_name | — | — | — | — | — | — | — | — | — |
| buyer_tax_id | — | — | — | — | — | — | — | — | — |
| subtotal | — | — | — | — | — | — | — | — | — |
| tax_amount | — | — | — | — | — | — | — | — | — |
| total_amount | — | — | — | — | — | — | — | — | — |
| currency | — | — | — | — | — | — | — | — | — |

Wrong value while both sides are PRESENT: **FP and FN**. Label title: **exact-value extraction** precision/recall/F1, not presence-only.

## 4. Row and grouping ablation E2

| Frozen evidence cohort | Baseline row-producing geometry version | Candidate opt-in variant | Gold rows | Predicted rows | Spatial matches | Row P/R/F1 | Complete-line | Complete-table | Counts of false row/cell matches | Artifact |
|---|---|---|---|---|---|---|---|---|---|---|
| Reviewed development source + fixed OCR evidence | TBD | TBD | — | — | — | — | — | — | — | NOT SCORED |

Paired baseline/candidate use exactly the same frozen Reader output. The row-matching policy is preregistered and **value-blind**. A flat list has no row assignment; report it qualitatively rather than assigning invented row F1.

## 5. Paired routing E1

| Source PDF ID and SHA | OCR-all terminal status | Route-aware status | OCR-all complete invoice | Route-aware complete invoice | OCR-all latency (s) | Route-aware latency (s) | Fallback | Failure code |
|---|---|---|---|---|---|---|---|---|
| TBD | — | — | — | — | — | — | — | — |

Aggregate paired outcomes: both correct / only OCR-all correct / only route-aware correct / both incorrect; median latency difference and range/CI (only where independence supports). **No blanket “accuracy preserved” or superiority conclusion** without supported measurements.

## 6. Normalization E3 and quality E5

Keep source values, raw candidates, minimal-parser canonical outputs, proposed normalized outputs and warnings separately. Both parsers use identical selected strings and canonical gold; report correct→wrong, wrong→correct and wrong→wrong transitions, missing/rejected outputs and introduced false values. Raw transcription exactness is a separate target/task. Warning counts require independent error labels to establish usefulness. Missing source transcripts produce unavailable CER/WER, not zero error.

| Parent / condition | Baseline field exact | Variant field exact | Rows complete | Source route | OCR CER/WER if available | Failure code | Artifact |
|---|---|---|---|---|---|---|---|
| Parent clean | — | — | — | — | — | — | — |
| Same parent blur/noise | — | — | — | — | — | — | — |
| Same parent rotated | — | — | — | — | — | — | — |

## 7. Taxonomy and adjudication

Assign a **primary root-cause stage** per failed original, and optional secondary tags: SOURCE_ROUTING; TEXT_RECOGNITION; OCR_ORDER_GEOMETRY; FIELD_CANDIDATE; FIELD_CLASSIFICATION; NORMALIZATION; ROW_DETECTION; ROW_ALIGNMENT; ARITHMETIC_CONSISTENCY; ORIGINAL_DATA_OR_LABEL_ERROR; UNSUPPORTED_LAYOUT; RUNTIME_FAILURE; REVIEW_EXPORT (workflow only). Record sample ID, source hash, independent reviewer, actual prediction and source gold, explanation and linked reproducible evidence. Do not quietly remove annotation disagreements.

| Original ID | Primary category | Stage | Gold vs immutable machine result | Source-region evidence | Reviewer | Reproduction artifact | Action |
|---|---|---|---|---|---|---|---|
| TBD | — | — | — | — | — | — | — |

## 8. Development engineering evidence (NOT accuracy)

- Updated TV3 [PR #65](https://github.com/vietreceipt-team/vietreceipt/pull/65), head `3ea5c99`, reports 40 real Reader runs on 20 v0.2 validation inputs (five parents, one family). The earlier 54-run v0 result is historical and must not be pooled with this cohort. Raw-reference CER/WER are affected by reference reading order; any post-hoc source-order control stays separately labeled. Neither establishes complete-invoice accuracy or stable latency improvement.
- TV2 [PR #66](https://github.com/vietreceipt-team/vietreceipt/pull/66) reports 30 base synthetic invoices, 510 generated files/variants and automated schema/integrity QA; not independent accuracy.
- Merged TV4 [PR #69](https://github.com/vietreceipt-team/vietreceipt/pull/69) reports 58/80 variant inputs with line rows versus 0 baseline in its development replay, **output counts only**; 0/80 independently reviewed, accuracy and effect size not measured. Open #71 extends counters/edge tests; it does not approve gold.
- Merged TV5 [PR #70](https://github.com/vietreceipt-team/vietreceipt/pull/70) reports a 20-record `PENDING_REVIEW` source plan: guard returns exit 2, evaluated 0 and metrics null; correct safety behavior, **not** benchmark success. Its three-route acceptance and TV6 [PR #68](https://github.com/vietreceipt-team/vietreceipt/pull/68)'s four real browser workflows on main `07c7cd0` establish synthetic workflow evidence only; row omissions and user effort require separate acceptance.

**Decision-to-claim trace:** no quantitative claim about Vietnamese invoices, independent mocks, complete invoice accuracy or time savings may be based on the development bullets.

## 9. Results to write after scoring

A complete finding paragraph must contain: *“On [dataset snapshot and independent split], [n scoreable of N eligible] original invoices, [failure count], VietReceipt achieved [metric numerator/denominator], with [interval if appropriate]; compared with [paired baseline], the observed difference was [effect, limitations]. Source and code: [immutable artifact, hashes, revision].”*

If no valid final cohort is run, write “Not evaluated on independent held-out invoices” rather than borrowing synthetic smoke tests.
