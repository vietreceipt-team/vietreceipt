# VietReceipt Research Design

## Purpose

This document translates the product plan into a thesis-ready research design.

The project should not be presented as “we connected OCR, KIE and a web UI.” The thesis contribution is the **design and controlled evaluation of a multi-format, reviewable invoice-processing workflow**.

## Research questions

### RQ1 — Multi-format route-aware extraction
On the same eligible born-digital PDFs, does route-aware reading preserve end-to-end invoice correctness while reducing processing time compared with rasterizing every page and applying OCR? Report JPG/PNG and scanned-PDF outcomes as separate route strata; do not call them a paired method comparison unless the same file bytes were processed by both declared methods.

### RQ2 — Structured extraction under layout and quality shift
How accurately does the integrated pipeline recover canonical headers and structured line items across seen, unseen and independently authored templates and controlled image-quality conditions? Which route, OCR, normalization, row-detection and alignment failures account for the observed outcomes?

### RQ3 — Human-in-the-loop verification (optional)
In a small, approved pilot with fictional invoices, how does assisted review compare with manual processing in task time, final correctness and correction effort?

RQ3 is optional for the core technical thesis. It becomes a formal result only if an approved pilot is actually run. The protocol is specified in [user-study-protocol.md](user-study-protocol.md).

The exact experiment-to-metric definitions, denominator, freeze gates and report table plan are in [evaluation-matrix.md](evaluation-matrix.md). Co-owner approval is required before the final test is opened.

## Hypotheses

The project may test the following hypotheses. They must be reported as hypotheses, not assumed conclusions.

### H1 — Route-aware reading
For born-digital PDFs, direct text/position extraction will preserve or improve extraction accuracy while reducing latency compared with rasterizing the PDF and applying OCR to every page.

### H2 — Structured line-item grouping
A proposed row-producing grouping method will improve complete-line or complete-table correctness over the current geometry-based row-grouping baseline on the same frozen OCR evidence. A flat value list may be shown qualitatively, but it cannot receive a row/complete-line score because it has no row assignments.

### H3 — Template shift
End-to-end accuracy will decrease on unseen templates relative to seen templates; the size and error profile of this drop quantify layout generalization.

### H4 — Controlled degradation
Image degradation will cause measurable performance loss, and the error taxonomy will identify which pipeline stages are most sensitive.

### H5 — Assisted review
If tested with users, VietReceipt-assisted review can reduce direct effort while preserving final correctness relative to manual entry/review.

## Contribution claims

The final thesis should separate **implemented contributions** from **measured contributions**.

### Implemented contribution candidates
- source-aware routing between direct PDF extraction and OCR;
- canonical evidence representation shared by PDF/OCR paths;
- structured header + tax + row-level line-item schema;
- evidence-linked human review with immutable machine output;
- consistency checks and explicit missing/unreadable/ambiguous states;
- reproducible experiment provenance and frozen manifests.

### Measured contribution candidates
Only claim these after experiments:
- accuracy/latency difference of route-aware vs OCR-all reading;
- line-item grouping improvement;
- robustness under controlled degradation;
- generalization gap between seen and unseen templates;
- user-effort difference in a pilot.

## Primary endpoint

The thesis headline metric is **end-to-end invoice correctness on frozen held-out data**, with source-file failures included in the eligible-document denominator.

Module scores such as OCR CER/WER or field-level F1 support diagnosis, but they must not replace the primary endpoint.

Recommended primary outputs:
- complete-header accuracy;
- complete-line accuracy;
- complete-invoice accuracy explicitly scoped to **13 supported headers + line items** until tax-group gold is added and validated;
- pipeline failure rate.

## Experimental units

The experimental unit is an **invoice document/base document**, not an augmented image.

All derivatives of one base invoice remain in the same split.

For synthetic generalization experiments, template identity must be split before instance generation/augmentation.

## Core experiment matrix

| Experiment | Baseline/control | Proposed/final | Main outcomes |
| --- | --- | --- | --- |
| E1 source routing | OCR-all | route-aware PDF/OCR | end-to-end accuracy, latency, failures |
| E2 line items | current row-producing geometry baseline | one proposed row-producing grouping method, same OCR evidence | row precision/recall/F1, cell exactness, complete-line/table accuracy |
| E3 normalization | raw extracted values | normalized + consistency checks | normalized exact match, false normalization count |
| E4 generalization | seen-template validation | unseen-template test | complete-header/invoice accuracy, error gap |
| E5 robustness | clean inputs | controlled degradation slices | accuracy delta by degradation |
| E6 independent challenge | generator-derived test | independent mock test | generalization outside generator assumptions |
| E7 user pilot (optional) | manual workflow | VietReceipt-assisted review | time, final correctness, corrections |

## Test hygiene

Before opening final test results:
- source routing policy frozen;
- OCR configuration frozen;
- extraction/ranking rules frozen;
- line grouping logic frozen;
- normalization/check rules frozen;
- evaluation code/metric definitions frozen.
- source-gold labels/file hashes frozen independently of OCR;
- OCR-aligned gold records reader run/block mapping without changing source labels;
- TV2/TV4/TV5 sign-off on eligibility, UNKNOWN, failure and tax-scope rules in [evaluation-matrix.md](evaluation-matrix.md).

If final-test results lead to algorithm changes, the changed system requires a new untouched confirmation set before a “final” claim.

## Reporting

Every thesis result should answer:
1. What exact data were used?
2. Was the template seen during development?
3. Was the data public, synthetic, independent mock or real?
4. What configuration/commit produced the result?
5. What is the sample count?
6. What is the uncertainty/limitation?
7. What common failures remain?
8. How many eligible inputs failed or lacked scoreable gold, and were any human corrections included? Machine predictions and reviewed outputs must remain separate.

## User-requirement traceability

The accountant survey should be used as requirement evidence, not as model-training data.

Examples:
- need to re-enter/search information → extraction + source-linked review;
- important totals/tax/items → prioritize these fields in evaluation;
- desire to inspect uncertain predictions → explicit review state and evidence;
- desire to see source context → document-side highlighting;
- line-item importance → row-level output is core, not optional.

The survey sample is small and should be described as formative requirements research, not representative population evidence.

## Thesis narrative

A recommended thesis structure:

1. Problem and accountant requirements
2. Related work and gaps
3. Research questions and dataset protocol
4. System design
5. Baselines and proposed workflow
6. End-to-end experiments
7. Generalization and robustness
8. Error analysis
9. Human-in-the-loop pilot, if conducted
10. Limitations and conclusions

The report should avoid a chapter sequence that merely mirrors implementation modules unless those modules answer the research questions.
