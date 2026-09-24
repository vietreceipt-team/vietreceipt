# VietReceipt — Project Plan v3

Date: 24/09/2026

## 1. Goal

Build and evaluate a web-based system that supports accountants in turning Vietnamese invoices into a consistent structured representation. The system must let a user inspect the source document, review machine-extracted values, correct them, confirm the result and export structured data.

The project is both a **prototype** and an **evaluation study**. It must not claim universal support for every Vietnamese invoice template or enterprise workflow.

The research emphasis is not “which OCR/model is best” in isolation. The main object of evaluation is the complete invoice-processing workflow:

```text
document
→ route by source type
→ text/OCR evidence
→ field + line-item extraction
→ normalization + consistency checks
→ human review
→ structured export
```

## 2. Research questions

### RQ1 — Multi-format extraction
How accurately can VietReceipt extract and normalize invoice information from:
- born-digital PDFs with usable text;
- scanned PDFs;
- images / digitized paper?

### RQ2 — Generalization and robustness
How much does performance change when:
- the invoice template/layout was not seen during development;
- input quality degrades through blur, noise, rotation, perspective or scan-like artifacts?

### RQ3 — Human verification
When a small user pilot is feasible, does the review interface help users complete accurate invoice data with fewer corrections or less direct interaction time than a comparable manual workflow?

RQ3 is optional for the core technical acceptance. No time-saving claim is allowed without an actual manual-vs-tool study.

## 3. Inputs

Supported business input groups:

1. paper invoice that is first photographed/scanned;
2. image already available as a digital file;
3. PDF, with direct text extraction preferred when a usable text layer exists and OCR used for scans/images.

Paper and image may share the same image/OCR pipeline after digitization. A photographed paper invoice is still identified as originating from paper for workflow reporting.

## 4. Core output

Canonical header fields:

- invoice template number;
- invoice symbol;
- invoice number;
- invoice date;
- seller name, tax ID and address;
- buyer name and tax ID;
- subtotal;
- tax amount;
- total amount;
- currency.

Structured content:

- tax-rate groups / tax breakdown when present;
- **line items grouped into records** with description, unit, quantity, unit price and amount;
- source/provenance and OCR evidence;
- raw, normalized, corrected/effective values and review state where applicable.

A line item must remain a row-level record. Returning five unrelated lists of descriptions, quantities and prices is not considered line-item extraction.

## 5. Product requirements

The core demo must support:

- upload image and PDF;
- digitized-paper workflow description/demo;
- PDF text-path and image/OCR path;
- header-field and basic line-item extraction;
- source document displayed beside structured output;
- evidence highlighting from extracted values back to source regions;
- explicit missing/unreadable/ambiguous/review states;
- user correction and confirmation;
- CSV/XLSX/JSON export;
- clear errors and documented limits.

Optional after the core flow is stable:

- small batch upload;
- date/seller filtering;
- duplicate warning;
- difficult/multi-page tables;
- less common fields.

Out of scope for the core version:

- automatic access to tax portals or third-party accounts;
- direct MISA/FAST/BRAVO integration;
- automatic accounting entries;
- legal/signature validation;
- a dedicated mobile scanning application;
- claiming support for every invoice layout;
- training a full OCR engine from scratch.

## 6. Dataset strategy

The project does not require the team to manually collect hundreds of real business invoices.

Primary development/evaluation sources:

- Vietnamese Bill Extraction public dataset;
- CORD public dataset;
- SROIE public dataset;
- VietReceipt Synthetic dataset produced by the team;
- VietReceipt Independent Mock Test produced separately from the main synthetic generator.

Exact dataset revisions, licenses, mapping rules and usable sample counts are frozen by TV2 before benchmark results are reported.

Synthetic examples and augmented variants are always labeled as synthetic. Public datasets retain their original provenance. No public/synthetic result may be described as proof of real-world enterprise performance.

### Split requirement

For the VietReceipt synthetic family, the split must be **template-disjoint** for the generalization experiment. Final unseen-template layouts must not be used to design extraction rules, prompts, thresholds or preprocessing.

Variants derived from one base document remain in the same split.

The independent mock test is designed separately from generator templates and stays untouched until the final evaluation phase.

## 7. Required experimental design

The project must include controlled comparisons, not only one final pipeline score.

Minimum experiment matrix:

1. **Reading baseline**
   - B0: OCR-all — send every PDF/image through rasterization + OCR.
   - P1: route-aware — direct PDF text extraction for usable born-digital PDF, OCR for scans/images.

2. **Line-item contribution**
   - B1: flat field extraction without row grouping.
   - P2: structured line-item grouping.

3. **Normalization/check contribution**
   - A0: extraction before normalization/consistency checks.
   - A1: final pipeline with normalization/checks.

4. **Generalization**
   - seen-template validation;
   - unseen-template final test;
   - independent mock final test.

5. **Robustness**
   - clean;
   - blur/noise;
   - rotation/perspective;
   - scan-like / compression when available.

All comparisons must use the same eligible sample set when claiming one method improves another.

## 8. Team

| Member | Primary ownership |
| --- | --- |
| TV1 | coordination, requirements, research questions, acceptance criteria, experiment matrix, final demo/report |
| TV2 | dataset/version management, synthetic + mock data, mapping/ground truth, split control, benchmark tables |
| TV3 | source routing, PDF extraction, preprocessing, OCR, OCR evidence and benchmark |
| TV4 | KIE, structured line items, normalization, consistency checks and field-level error analysis |
| TV5 | backend, file/result persistence, processing orchestration, experiment provenance, export and backend tests |
| TV6 | frontend upload/review/correction/confirmation/export UX and review telemetry |

Everyone contributes to testing, documentation and the final report.

## 9. Timeline

### Weeks 1–2
Freeze research questions, dataset versions, schema/API, project scope and UI flow. Produce at least one end-to-end example from file upload to structured result. Build an initial synthetic generator and define template-disjoint splits.

### Weeks 3–4
Benchmark OCR-all vs route-aware PDF/OCR reading. Implement header extraction and the first structured line-item path. Integrate backend and frontend against shared fixtures.

### Weeks 5–6
Complete image/PDF flows, basic line items, normalization/checks, source-view review, correction, confirmation and CSV/XLSX/JSON export. Create the independent mock-test set.

### Weeks 7–8
Perform error analysis, improve weak fields, QA dataset mappings, and freeze final unseen-template + independent mock manifests.

### Weeks 9–10
Freeze configuration and run final end-to-end benchmarks, baseline/ablation experiments, robustness slices and latency measurements. Run a small user pilot only if participant consent and comparable tasks are available.

### Weeks 11–12
Fix demo blockers, verify reproducibility, finish report, slides, video and release package. Ensure every headline claim maps to a reported experiment.

### Weeks 13–16 optional
Add templates/datasets, difficult tables, batch processing and an independent extension evaluation.

## 10. Evaluation principles

- The **primary headline result is end-to-end performance**, not the best module score.
- Never tune on the final test split.
- Report per dataset/source and per field; do not hide weak fields behind one aggregate.
- Keep OCR metrics separate from KIE metrics.
- Evaluate line-item detection and cell correctness separately.
- Report complete-header / complete-invoice correctness.
- Report seen-template and unseen-template results separately.
- Report robustness by degradation slice.
- Run baseline/ablation comparisons on the same frozen eligible samples.
- Report system latency separately from any user interaction time.
- Do not claim time savings for accountants unless a real comparison study is actually conducted.
- Preserve raw machine output separately from user-corrected output.

## 11. Definition of core completion

The 12-week version is ready for acceptance when:

1. a supported image/PDF can travel through the full pipeline;
2. PDF text and image/OCR routes both function;
3. the output includes structured header fields and grouped basic line items;
4. the user can inspect source evidence, correct, confirm and export;
5. the team can reproduce frozen end-to-end benchmark results;
6. at least one baseline/ablation experiment and one unseen-template evaluation have been completed;
7. all claims in the report are limited to evidence actually measured.
