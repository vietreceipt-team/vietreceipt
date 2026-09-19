# VietReceipt — Project Plan v2

Date: 19/09/2026

## 1. Goal

Build a web-based tool that supports accountants in turning Vietnamese invoices into a consistent structured representation. The system must let a user inspect the source document, review machine-extracted values, correct them, confirm the result and export structured data.

The project is a prototype and evaluation study. It must not claim universal support for every Vietnamese invoice template.

## 2. Inputs

Supported business input groups:

1. paper invoice that is first photographed/scanned;
2. image already available as a digital file;
3. PDF, with direct text extraction preferred when a usable text layer exists and OCR used for scans/images.

Paper and image may share the same image/OCR pipeline after digitization. A photographed paper invoice is still identified as originating from paper for workflow reporting.

## 3. Core output

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
- line items with description, unit, quantity, unit price and amount;
- source/provenance and OCR evidence;
- raw, normalized, corrected/effective values and review state where applicable.

## 4. Product requirements

The core demo must support:

- upload image and PDF;
- digitized-paper workflow description/demo;
- PDF text-path and image/OCR path;
- header-field and basic line-item extraction;
- source document displayed beside structured output;
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

## 5. Dataset strategy

The project does not require the team to manually collect hundreds of real business invoices.

Primary development/evaluation sources:

- Vietnamese Bill Extraction public dataset;
- CORD public dataset;
- SROIE public dataset;
- VietReceipt Synthetic dataset produced by the team.

Exact dataset revisions, licenses, mapping rules and usable sample counts are frozen by TV2 before benchmark results are reported.

Synthetic examples and augmented variants are always labeled as synthetic. Public datasets retain their original provenance. No public/synthetic result may be described as proof of real-world enterprise performance.

## 6. Team

| Member | Primary ownership |
| --- | --- |
| TV1 | coordination, requirements, acceptance criteria, evaluation plan, final demo/report |
| TV2 | dataset/version management, synthetic data, mapping/ground truth, split control, evaluation tables |
| TV3 | PDF extraction, preprocessing, OCR, OCR evidence and benchmark |
| TV4 | KIE, line items, normalization, consistency checks and field-level error analysis |
| TV5 | backend, file/result persistence, processing orchestration, export and backend tests |
| TV6 | frontend upload/review/correction/confirmation/export UX |

Everyone contributes to testing, documentation and the final report.

## 7. Timeline

### Weeks 1–2
Freeze dataset versions, schema/API, project scope and UI flow. Produce at least one end-to-end example from file upload to structured result. Build an initial synthetic generator and map a small public-data subset to the canonical schema.

### Weeks 3–4
Benchmark the selected OCR/PDF approach. Implement header extraction and the first basic line-item path. Integrate backend and frontend against shared fixtures.

### Weeks 5–6
Complete image/PDF flows, basic line items, normalization/checks, source-view review, correction, confirmation and CSV/XLSX/JSON export.

### Weeks 7–8
Perform error analysis, improve weak fields, QA dataset mappings, freeze final test splits and harden UI/error handling.

### Weeks 9–10
Freeze configuration and run final benchmarks only on the designated final splits. Measure processing latency and end-to-end demo behavior.

### Weeks 11–12
Fix demo blockers, verify reproducibility, finish report, slides, video and release package.

### Weeks 13–16 optional
Add templates/datasets, difficult tables, batch processing and an independent extension evaluation.

## 8. Evaluation principles

- Never tune on the final test split.
- Report per dataset/source and per field; do not hide weak fields behind one aggregate.
- Keep OCR metrics separate from KIE metrics.
- Evaluate line-item detection and cell correctness separately.
- Report system latency separately from any user interaction time.
- Do not claim time savings for accountants unless a real comparison study is actually conducted.
- Preserve raw machine output separately from user-corrected output.

## 9. Definition of core completion

The 12-week version is ready for acceptance when a supported image/PDF can travel through the full pipeline, the user can inspect/correct/confirm the structured result, export it, and the team can reproduce benchmark results from documented dataset versions and frozen splits.
