# VietReceipt

**VietReceipt** là web demo hỗ trợ kế toán trích xuất, chuẩn hóa, đối chiếu, chỉnh sửa và xuất dữ liệu từ hóa đơn Việt Nam.

## Project baseline — 19/09/2026

- Nhóm: **6 thành viên**.
- Thời gian: **12 tuần cốt lõi**, có thể mở rộng đến tuần 16 nếu có đủ 4 tháng.
- Input nghiệp vụ: **hóa đơn giấy đã số hóa, ảnh chụp/ảnh quét, PDF có text hoặc PDF scan**.
- Output: dữ liệu hóa đơn theo schema chung, màn hình review human-in-the-loop, CSV/XLSX/JSON.
- Dataset strategy: **public datasets + synthetic Vietnamese invoices**. Thu thập hàng trăm hóa đơn thật **không còn là điều kiện bắt buộc**.
- Không tuyên bố hiệu quả trên dữ liệu doanh nghiệp thực tế nếu chưa có tập đánh giá thực tế tương ứng.

## Canonical invoice scope

### Header fields

- `invoice_template_number`
- `invoice_symbol`
- `invoice_number`
- `invoice_date`
- `seller_name`
- `seller_tax_id`
- `seller_address`
- `buyer_name`
- `buyer_tax_id`
- `subtotal`
- `tax_amount`
- `total_amount`
- `currency`

### Structured content

- tax breakdown / tax-rate groups when present
- line items: description, unit, quantity, unit price, amount
- source/provenance, raw value, normalized value, confidence/review state, OCR evidence

A missing field must remain distinguishable from an unreadable or ambiguous field. The system must never invent a value without traceable evidence.

## Web demo flow

```text
Upload image/PDF
→ classify/read source
→ OCR or direct PDF text extraction
→ KIE / field extraction
→ normalization + consistency checks
→ review source beside extracted data
→ edit / confirm
→ export CSV/XLSX/JSON
```

PDF with usable text should be parsed directly first. OCR is used for image-based content or scanned PDF.

## Dataset strategy

Development uses four dataset families:

1. **Vietnamese Bill Extraction** — Vietnamese bill/receipt examples for Vietnamese extraction work.
2. **CORD** — public receipt dataset for layout/line-item prototyping and benchmark experiments.
3. **SROIE** — public scanned-receipt benchmark for OCR/KIE comparison.
4. **VietReceipt Synthetic** — generated Vietnamese invoice templates with automatic ground truth and controlled distortions.

Synthetic/public data must keep dataset provenance and split identity. Synthetic variants of one base document stay in the same split. Final metrics must name the exact dataset/version/split used.

See `docs/dataset-strategy.md`.

## Architecture

```text
Frontend
  ↓ REST / multipart
FastAPI Backend
  ↓
Processing orchestration / worker
  ├─ PDF text extraction
  ├─ image preprocessing
  ├─ OCR
  ├─ KIE + normalization
  └─ consistency checks
  ↓
PostgreSQL + object storage
  ↓
Review / corrections / confirmation / export
```

The asynchronous worker design, immutable OCR/KIE run provenance and human review flow from the earlier implementation may be reused. The old **five-field receipt contract is superseded** by the invoice contract in this README and `docs/integration-contracts.md`.

## Team roles

| Role | Main responsibility |
| --- | --- |
| TV1 — Leader / BA / Evaluation | scope, backlog, acceptance, demo, report, integration decisions |
| TV2 — Dataset & Evaluation | public datasets, synthetic dataset, mapping/ground truth, split/version control, benchmark tables |
| TV3 — OCR / PDF | image/PDF reading, preprocessing, OCR benchmark, text + position evidence |
| TV4 — KIE / Normalization | invoice fields, tax/line items, normalization, consistency checks, extraction evaluation |
| TV5 — Backend | API, persistence, orchestration, export, processing status, integration tests |
| TV6 — Frontend | upload, source viewer, editable review UI, line-item review, confirm/export flow |

## 12-week core roadmap

- **W1–2:** freeze scope, dataset versions, canonical schema/API, synthetic generator baseline, one end-to-end invoice.
- **W3–4:** OCR/PDF baseline, KIE header baseline, first line-item extraction, backend/frontend integration.
- **W5–6:** complete three input paths, normalization/checks, editable review and export.
- **W7–8:** error analysis, data/version QA, line-item hardening, freeze final public test splits.
- **W9–10:** final benchmark on frozen splits; latency and end-to-end workflow evaluation.
- **W11–12:** demo hardening, reproducibility, report, slides, video and release package.
- **W13–16 optional:** more templates/datasets, difficult tables, batch processing and independent extension evaluation.

## Authoritative documents

- `docs/project-plan.md`
- `docs/dataset-strategy.md`
- `docs/architecture.md`
- `docs/integration-contracts.md`
- `docs/evaluation-plan.md`
- `schemas/invoice-kie-result.v2.schema.json` (target v2)
- `schemas/invoice-annotation.v2.schema.json` (target v2)
- `schemas/ocr-result.schema.json`

See `docs/migration-status.md` for the v1-runtime → v2-target transition. Historical Week-1/2/3 documents and closed issues may remain in Git history for traceability, but they are not current requirements.
