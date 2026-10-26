# VietReceipt — thesis manuscript working draft (TV1)

**Date:** 2026-10-24. **Owner:** TV1. **Status:** research-writing draft, not advisor-approved. **Working title:** *VietReceipt – Design and Evaluation of a Multi-format Vietnamese Invoice Information Extraction and Standardization System*.

> **Evidence policy:** This document describes implementation from the repository and an experimental *plan*. The words “expected”, “hypothesized” and “proposed” are deliberate. No end-to-end extraction accuracy, independent mock accuracy, user time saving, or final test result is claimed without verified experiment output. References to development tests are engineering evidence only. Project screenshots and student-specific rubric/bibliographic formatting need final insertion.

## Abstract (draft — update only after experiments)

Vietnamese invoices vary in file representation and layout. Their automatic processing requires not only readable text but also correctly associated header attributes and product rows. This thesis designs VietReceipt, a multi-format document-processing and human-verification system. The system receives image files, born-digital PDFs and scanned PDFs, routes each input to suitable reading methods, converts text and geometry into a common evidence representation, and extracts 13 canonical invoice header fields and structured five-cell line items. Immutable machine results remain separate from corrections and verified exports. To investigate the approach, the thesis defines paired route-aware versus OCR-all reading experiments, row-grouping baseline comparisons, layout-shift and quality-degradation analyses, and original-file end-to-end correctness metrics. An optional user study is designed but is not a substitute for technical accuracy testing. **Measured results and quantified conclusions will be added only after the approved experiments are run.**

*Keywords:* Vietnamese invoice understanding; OCR; key information extraction; structured line items; document routing; reproducible evaluation; human verification.

## 1. Introduction

### 1.1 Motivation and problem

In practical invoice handling, an output containing all relevant-looking values is not necessarily useful: amounts can be attached to the wrong row, the document may contain unreadable elements, and a recognized string may correspond to a neighboring label. Input diversity compounds this problem. For born-digital PDFs a text layer can offer reading and position information; images and scanned PDFs typically require OCR. Downstream extraction must normalize the resulting evidence while preserving provenance and any uncertainty.

VietReceipt addresses this by connecting source-aware reading to canonical header and line-item extraction, correction, verification and structured export. The core claim is not that integrating OCR creates a new OCR model, but that a unified, evidence-preserving workflow can be built and evaluated at the **original-file level**, including failures and row reconstruction.

### 1.2 Research gap

OCR metrics alone cannot tell whether a seller name, date and final total are assigned to their correct semantic roles. Flat KIE values are insufficient when quantities and prices need to be linked to descriptions. Performance on a generator’s familiar layouts is not proof of transfer to independently authored layouts. Last, a browser workflow that permits corrections does not automatically establish whether corrections improve user efficiency.

This thesis therefore separates (a) document reading, (b) schema-constrained semantic extraction and row structure, (c) end-to-end correctness, and (d) human review. It also separates **system implementation evidence** from **measured research evidence**.

### 1.3 Research questions

- **RQ1 (routing trade-off):** For the same born-digital PDF inputs, what are the paired changes in complete-invoice correctness, terminal processing time and failure rate when using route-aware reading instead of OCR-all? Image and scanned-PDF results are separate route strata.
- **RQ2 (structured extraction and generalization):** How reliably can a unified pipeline recover 13 canonical header fields and fully linked five-cell rows on seen, unseen, degraded and independently authored invoice layouts, and which stages explain errors?
- **RQ3 (optional human verification):** In a small supervised pilot using fictional invoices, how do manual and assisted workflows compare on final correctness, completion time and correction effort? RQ3 becomes a result only if approved and run.

### 1.4 Objectives and deliverables

1. Implement supported image/PDF routes into a common evidence contract.
2. Extract canonical invoice fields, line structure and review flags without inventing unsupported values.
3. Preserve machine outputs independently from review edits and exports.
4. Define source-grounded, reproducible baseline/ablation and failure-aware evaluation.
5. Provide a repeatable demo and report both successes and limitations.

### 1.5 Contribution boundary

**Implemented/design contributions:** route-aware Reader, canonical OCR-to-KIE evidence interface, 13-field and structured-row output, normalization/consistency checks, review/edit/verify/export workflow, versioned evaluation and artifact provenance.

**Only after measured evidence:** increased speed, improved row accuracy, robustness, generalization and reduced human effort. Until then these remain hypotheses, not demonstrated contributions.

## 2. Related Work

### 2.1 Receipt parsing datasets

The [CORD dataset](https://github.com/clovaai/cord) provides Indonesian receipt images, text/boxes and hierarchical receipt annotations; its v2 improves parsing hierarchy with subgroup identifiers. It motivates evaluating line identity and relationships rather than a bag of recognized tokens. Dataset language and document type limit direct extrapolation to Vietnamese tax invoices.

The [ICDAR 2019 SROIE competition](https://rrc-red.cvc.uab.es/?ch=13&com=tasks), described by [Huang et al.](https://arxiv.org/abs/2103.10213), separates text localization, OCR and four-field key extraction on scanned receipts. It motivates staged error analysis and explicitly scoped metrics. Its field set does not directly cover VietReceipt’s canonical tax headers and five-cell rows.

### 2.2 Layout-aware and OCR-free methods

[LayoutLMv3](https://arxiv.org/abs/2204.08387) investigates unified text/image pretraining and cross-modal alignment for document AI, showing why token content and spatial appearance are relevant to extraction. [Donut](https://www.ecva.net/papers/eccv_2022/papers_ECCV/html/8042_ECCV_2022_paper.php) proposes OCR-free document understanding, motivating study of OCR error propagation and model/pipeline alternatives. These are **related methods, not models implemented or benchmarked by VietReceipt** unless a future experiment explicitly does so.

### 2.3 Structured table evaluation

[PubTables-1M](https://www.microsoft.com/en-us/research/publication/pubtables-1m/) addresses table ground-truth ambiguity and structure recognition. Although its source domain is largely scientific articles rather than Vietnamese invoices, its attention to cell structure and canonical annotation supports VietReceipt’s decisions to treat correct row association and gold consistency as first-class outcomes.

### 2.4 Positioning table

| Prior line of work | Useful lesson | VietReceipt response | What must not be claimed |
|---|---|---|---|
| CORD | Multilevel receipt/row structure | Annotate and match line identity, then five required cells | Indonesian receipts validate Vietnamese VAT invoices |
| SROIE | Differentiate OCR and key extraction | Report CER/WER separately from source-grounded KIE | Four-field SROIE score equals 13-field accuracy |
| LayoutLMv3 | Layout + text matter | Keep OCR geometry/evidence with content | VietReceipt trains or outperforms LayoutLMv3 |
| Donut | OCR-based pipelines propagate reading errors | Evaluate OCR-all vs route-aware, track source failures | OCR-free baseline was tested here |
| PubTables-1M | Table structures need canonical gold | Evaluate complete lines/tables with region-based matches | PubTables trained on Vietnamese invoices |

## 3. System Design and Implementation

### 3.1 Architecture

The repository documents the following logical implementation:

```text
Browser (source viewer, correction, verification)
  -> multipart/REST API (FastAPI)
  -> processing orchestration (outbox, Redis/Celery worker)
      -> source detection and route selection
      -> PDF direct text with geometry OR OCR from images/scan
      -> unified OCR/document evidence, page/block identifiers
      -> KIE v2: 13 header fields, five-cell item rows
      -> normalization and arithmetic/consistency warnings
  -> PostgreSQL metadata/runs and source object storage
  -> immutable machine snapshot | separately stored human corrections
  -> JSON / CSV / XLSX export
```

The specific runtime/dependencies must be captured from the final system build rather than guessed from a schematic. The worker/provider configuration and known ARM64 OCR limitations are documented in [the reproducible demo guide](v2-reproducible-demo.md).

### 3.2 Three input paths and evidence

- **Image (JPG/PNG):** decode/preprocess where appropriate, run OCR, preserve text/block boxes, page and confidence meaning.
- **Text PDF:** attempt usable native text/position extraction; record native-text decision and fallbacks. This route permits a matched OCR-all control on the same PDF.
- **Scanned PDF:** rasterize/recognize the image content, map recognized text and coordinates back to the canonical source frame.

All routes feed one KIE contract. OCR provenance is not equivalent to source-gold validation; evidence IDs identify a model/Reader run, not a universal text annotation.

### 3.3 Canonical output

The **13 headers** are:
`invoice_template_number`, `invoice_symbol`, `invoice_number`, `invoice_date`, `seller_name`, `seller_tax_id`, `seller_address`, `buyer_name`, `buyer_tax_id`, `subtotal`, `tax_amount`, `total_amount`, `currency`.

Each structured line item has `description`, `unit`, `quantity`, `unit_price`, `amount`. Complete-invoice research scoring covers these headers plus all row cells/associations. The product may represent **tax breakdown groups**, but these are **not included in strict accuracy** until an independently reviewed tax-group source-gold contract exists.

Field states are `PRESENT`, `NOT_PRESENT`, `UNREADABLE`, `AMBIGUOUS`, `UNKNOWN`. In gold, `UNKNOWN` means unavailable/unadjudicated annotation and is excluded from its scoring denominator. In machine output, `UNKNOWN` can mean no supported candidate or an unresolved value; it is an actual prediction, not a reason to discard a known gold target. Neither meaning establishes source absence. Currency/date/numeric normalization is deterministic where justified and must preserve source/raw evidence.

### 3.4 Human-in-the-loop verification

The browser surfaces source evidence alongside predicted values and allows corrections before verification/export. An immutable pre-edit machine snapshot provides a fair AI denominator. Final reviewed values and edits form a separate human-workflow artifact. Confidence is not assumed calibrated. Product evidence should include a case that requires correction rather than only a flawless synthetic invoice.

## 4. Methodology

### 4.1 Data sources and gold tiers

Data sources described in the repository include public Vietnamese Bill Extraction, CORD, SROIE, VietReceipt synthetic invoices and a planned independently authored mock final set. Each retains native schema and provenance. Cross-dataset comparisons are descriptive unless tasks/labels and annotation availability truly match.

**Source Gold** comes from original bytes (field status+value, row identity/cells and normalized source region), frozen independently of predictions. **OCR Evidence** records Reader output. **Aligned Gold** links locked source annotations to one frozen Reader run, with explicit unmatched evidence. Only Source Gold supports **original-file end-to-end** accuracy.

All derivatives from one original stay in the same data split, and template families used for independent evaluation must be disjoint from development. TV2’s development `test` partition is **not an untouched final test set**, because generator assumptions have been inspected.

### 4.2 Metric rules

Detailed equations are in [TV1 decisions](tv1-evaluation-decisions.md) and the [evaluation matrix](evaluation-matrix.md). Core metrics: field status+value exactness, value-aware precision/recall/F1, row detection P/R/F1, complete-line/table/header/invoice accuracy, coverage/UNKNOWN, processing failure rate, paired terminal latency and optional OCR CER/WER.

Source-level row matching must use independently annotated page regions, be one-to-one and **value-blind**. TV4’s positive-IoU candidate remains a development candidate until stress scenarios are reviewed. Wrong field-row associations count as incorrect even if the values happen to exist somewhere else.

An original that is eligible but crashes or yields no valid prediction remains a failure. A document with required gold `UNKNOWN` remains in eligible-processing counts but is excluded from the strict fully-scoreable denominator, with coverage disclosed. Do not use post-review values in machine accuracy.

### 4.3 Controlled experiments

| ID | Control | Candidate/condition | Primary report |
|---|---|---|---|
| E1 | OCR-all on each born-digital PDF | Route-aware on **identical bytes** | Complete accuracy trade-off, paired latency, failure and route counts |
| E2 | Current geometry row-producing baseline | Proposed row-producing variant, fixed OCR evidence | Row P/R/F1, complete-line/table, wrong-cell cases |
| E3 | Frozen minimal canonical parser | Proposed normalizer on identical selected strings and canonical gold | Paired gain/harm transitions and introduced false values; warnings separately |
| E4 | Seen layout families | Unseen families, after freeze | Generalization gap and error modes |
| E5 | Clean source | Frozen blur/noise/rotation/scan variants | Accuracy falloff and failure severity |
| E6 | Generator-derived development set | Independently authored mock set | Transfer gap under identical frozen algorithm |
| E7* | Manual review/entry | Assisted review on matched fictional tasks | Final correctness, time, edits (optional) |

*E7 is conditional on participant permission/approval; no participant evidence exists at draft time.*

### 4.4 Analysis plan and uncertainty

Use the **base invoice/document** as the experimental unit. Report n for eligible originals, scoreable originals, line counts, failures and distinct template families. Pair by exact source identity/hash when comparing reader/grouping methods. Do not claim statistical superiority from a small number of layouts; show descriptive paired differences and, when independent families permit, uncertainty intervals with registered resampling units and seed. Report unfavorable as well as favorable outcomes.

For RQ1, **there is no preapproved non-inferiority margin**; report the observed accuracy-versus-latency trade-off rather than “accuracy preserved without loss” by decree. For E2, compare two actual row-producing algorithms; never assign a row F1 score to a flat text-value baseline with no row objects.

### 4.5 Reproducibility

Each experiment should produce the source manifest and file hashes, dataset version, split/family IDs, reader/evaluator/KIE commits/configs, canonical geometry version, machine output, failure records, raw/result checksums, timing environment and metric numerator/denominator. Preserve exactly what was measured and avoid rewriting old artifacts to match newer run metadata.

## 5. Current Evidence (not final results)

As of the repository snapshot checked on 26 October 2026, main `07c7cd0`:
- Updated [TV3 PR #65](https://github.com/vietreceipt-team/vietreceipt/pull/65), head `3ea5c99`, reports 20 v0.2 validation inputs × two reading modes (40 real Reader runs), five parent invoices and one layout family. The earlier 54-run v0 capture is historical and is not pooled with this cohort. Transcript reading-order effects and limited layout diversity preclude formal held-out generalization or 13+row accuracy. Values here are **author-reported**, not rerun in this TV1 document.
- [TV2 PR #66](https://github.com/vietreceipt-team/vietreceipt/pull/66) contains a generator/registry and automated dataset artifacts; its dev data are not independently certified as final test.
- Merged [TV4 PR #69](https://github.com/vietreceipt-team/vietreceipt/pull/69) implements a candidate grouping/evaluator and reports **0/80 reviewed candidates**, so scored improvements and accuracy remain unavailable. Open [PR #71](https://github.com/vietreceipt-team/vietreceipt/pull/71) adds counters and regression evidence without approving gold.
- Merged [TV5 PR #70](https://github.com/vietreceipt-team/vietreceipt/pull/70) implements original-file source scoring, but its candidate plan remains `PENDING_REVIEW` and gate-blocked, with `metrics=null`.
- [TV6 PR #68](https://github.com/vietreceipt-team/vietreceipt/pull/68), head `e59f87d`, reports four real-browser synthetic workflows on the updated backend with immutable snapshots and parsed exports. It does not establish omitted-row recovery, independent invoice accuracy or participant time savings.

These are engineering-progress observations, **not thesis accuracy measurements**. A full results table is staged in [the results and analysis workbook](tv1-results-and-analysis.md).

## 6. Results — RESERVED FOR VERIFIED MEASUREMENTS

No verified independent original-file accuracy values are available to insert here. After acceptance, report per-route counts, 13-field metrics, row/cell correctness, E1 paired latency, E2 baseline/variant deltas, E4–E6 generalization/robustness slices, failures and uncertainty. Do not copy unrelated thesis/paper scores into VietReceipt results.

## 7. Discussion and Threats to Validity

**Internal validity:** inaccurate source annotations, leakage via shared generator templates, different Reader conditions, post-hoc threshold selection and missing failed samples can bias comparisons. **Construct validity:** OCR CER is not complete invoice correctness; presence-only scores are not exact-value correctness; evidence-block row matching is not source-region row matching. **External validity:** synthetic/foreign retail receipts do not necessarily represent Vietnamese enterprise invoice diversity; a small number of independent families constrains generalization claims. **System validity:** model/runtime differences, OCR native crashes on a tested Linux ARM64 environment, worker cold starts and PDF text-layer variations affect reproducibility. **Human study:** recruitment, learning/order effects and pilot size limit inference, even if a study is conducted.

The documented ARM64 crash containment preserves failure records; it does not mean OCR inference has been repaired. All figures should use artifact metadata and note runtime environment.

## 8. Conclusion — draft without fabricated results

VietReceipt offers a modular, source-aware design for processing different invoice formats into a reviewable canonical record. Its methodology explicitly distinguishes recognition, structured row reconstruction, full-document correctness and human corrections, while recording provenance and failures. Whether route-aware reading offers a favorable trade-off, whether grouping improves line correctness, and whether the workflow reduces user effort **remain empirical questions until a valid benchmark and any approved pilot are completed**. Future work can extend independent layout diversity, tax-group annotation and stronger learned structural baselines if data and evidence justify them.

## References — primary sources and implementation

1. Park, S. et al. (2019). *CORD: A Consolidated Receipt Dataset for Post-OCR Parsing*. Document Intelligence Workshop. https://github.com/clovaai/cord
2. Huang, Z. et al. (2021 preprint describing ICDAR 2019). *ICDAR2019 Competition on Scanned Receipt OCR and Information Extraction*. https://arxiv.org/abs/2103.10213
3. Huang, Y. et al. (2022). *LayoutLMv3: Pre-training for Document AI with Unified Text and Image Masking*. ACM Multimedia. https://arxiv.org/abs/2204.08387
4. Kim, G. et al. (2022). *OCR-Free Document Understanding Transformer (Donut)*. ECCV. https://www.ecva.net/papers/eccv_2022/papers_ECCV/html/8042_ECCV_2022_paper.php
5. Smock, B., Pesala, R., Abraham, R. (2022). *PubTables-1M: Towards Comprehensive Table Extraction from Unstructured Documents*. CVPR. https://www.microsoft.com/en-us/research/publication/pubtables-1m/
6. VietReceipt repository: [README](../README.md), [architecture](architecture.md), [dataset strategy](dataset-strategy.md), [evaluation matrix](evaluation-matrix.md), [integration contracts](integration-contracts.md), [demo and runtime guide](v2-reproducible-demo.md).

**Required editorial actions before submission:** review precise institutional rubric and advisor comments if made available; add verified figures/screenshots/architecture diagram and bibliography style; substitute all “reserved” result sections with artifact-backed numbers; verify final software/repo revisions and author contributions.
