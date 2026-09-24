# VietReceipt

**VietReceipt** là prototype và nghiên cứu đánh giá về hệ thống hỗ trợ kế toán trích xuất, chuẩn hóa, đối chiếu, chỉnh sửa và xuất dữ liệu từ hóa đơn Việt Nam đa định dạng.

## Project baseline — 19/09/2026

- Nhóm: **6 thành viên**.
- Thời gian: **12 tuần cốt lõi**, có thể mở rộng đến tuần 16 nếu có đủ 4 tháng.
- Input nghiệp vụ: **hóa đơn giấy đã số hóa, ảnh chụp/ảnh quét, PDF có text hoặc PDF scan**.
- Output: dữ liệu hóa đơn theo schema chung, màn hình review human-in-the-loop, CSV/XLSX/JSON.
- Dataset strategy: **public datasets + synthetic Vietnamese invoices + independent mock test set**. Thu thập hàng trăm hóa đơn thật **không còn là điều kiện bắt buộc**.
- Không tuyên bố hiệu quả trên dữ liệu doanh nghiệp thực tế nếu chưa có tập đánh giá thực tế tương ứng.

## Research positioning

VietReceipt không được định vị chỉ là một ứng dụng OCR. Mục tiêu nghiên cứu là đánh giá một pipeline end-to-end có routing theo loại tài liệu, trích xuất line items có cấu trúc và human-in-the-loop review.

Ba research questions chính:

1. **RQ1 — Multi-format extraction:** VietReceipt trích xuất và chuẩn hóa thông tin chính xác đến đâu trên PDF có text, PDF scan và ảnh?
2. **RQ2 — Generalization and robustness:** hiệu năng thay đổi thế nào trên layout chưa từng thấy và các mức suy giảm chất lượng như blur, noise, rotation, perspective?
3. **RQ3 — Human verification:** human-in-the-loop review có thể hỗ trợ người dùng hoàn thành dữ liệu chính xác hơn hoặc ít thao tác hơn so với quy trình không có hỗ trợ tự động hay không?

Đóng góp dự kiến phải được chứng minh bằng thí nghiệm, không chỉ bằng việc tích hợp nhiều model:

- **route-aware document reading:** direct PDF text extraction khi có text layer, OCR cho image/scan;
- **structured line-item reconstruction:** liên kết description, quantity, unit price và amount thành từng dòng;
- **reviewable structured output:** mọi giá trị quan trọng giữ evidence và trạng thái cần review;
- **controlled evaluation protocol:** held-out unseen-template test, degradation slices, baseline/ablation và end-to-end metrics.

Xem `docs/research-design.md` và `docs/evaluation-plan.md`.

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
→ line-item grouping
→ normalization + consistency checks
→ review source beside extracted data
→ edit / confirm
→ export CSV/XLSX/JSON
```

PDF with usable text should be parsed directly first. OCR is used for image-based content or scanned PDF.

## Dataset strategy

Development uses five dataset families / evaluation sources:

1. **Vietnamese Bill Extraction** — Vietnamese bill/receipt examples for Vietnamese extraction work.
2. **CORD** — public receipt dataset for layout/line-item prototyping and benchmark experiments.
3. **SROIE** — public scanned-receipt benchmark for OCR/KIE comparison.
4. **VietReceipt Synthetic** — generated Vietnamese invoice templates with automatic ground truth and controlled distortions.
5. **VietReceipt Independent Mock Test** — manually designed mock invoices that do not reuse the synthetic generator templates; reserved for independent final evaluation.

Synthetic/public data must keep dataset provenance and split identity. Synthetic variants of one base document stay in the same split. **Template families used for final unseen-template evaluation must not appear in development or validation.** Final metrics must name the exact dataset/version/split used.

See `docs/dataset-strategy.md`.

## Architecture

```text
Frontend
  ↓ REST / multipart
FastAPI Backend
  ↓
Processing orchestration / worker
  ├─ source routing
  ├─ PDF text extraction
  ├─ image preprocessing
  ├─ OCR
  ├─ KIE + line-item grouping
  ├─ normalization
  └─ consistency checks
  ↓
PostgreSQL + object storage
  ↓
Review / corrections / confirmation / export
```

The asynchronous worker design, immutable OCR/KIE run provenance and human review flow from the earlier implementation may be reused. The old **five-field receipt contract is superseded** by the invoice contract in this README and `docs/integration-contracts.md`.

## Evaluation principle

The main headline result must be **end-to-end invoice performance on frozen held-out data**, not the best score of an individual module.

Required reporting includes:

- OCR CER/WER where reference transcription exists;
- per-field exact match / precision / recall / F1 as appropriate;
- line detection recall and matched-line cell correctness;
- complete-header and complete-invoice accuracy;
- performance on seen vs unseen templates;
- robustness by degradation slice;
- processing latency and stage failure rate;
- baseline and ablation results using the same frozen data.

Module metrics are diagnostic evidence only. A high OCR or KIE score does not substitute for end-to-end evaluation.

## Team roles

| Role | Main responsibility |
| --- | --- |
| TV1 — Leader / BA / Evaluation | scope, backlog, research questions, acceptance, experiment matrix, demo, report, integration decisions |
| TV2 — Dataset & Evaluation | public datasets, synthetic/mock dataset, mapping/ground truth, template-disjoint split/version control, benchmark tables |
| TV3 — OCR / PDF | source routing, image/PDF reading, preprocessing, OCR benchmark, text + position evidence |
| TV4 — KIE / Normalization | invoice fields, line-item grouping, tax/line items, normalization, consistency checks, extraction evaluation |
| TV5 — Backend | API, persistence, orchestration, experiment provenance, export, processing status, integration tests |
| TV6 — Frontend | upload, source viewer, editable review UI, line-item review, confirm/export flow, review telemetry |

## 12-week core roadmap

- **W1–2:** freeze scope, research questions, dataset versions, canonical schema/API, synthetic generator baseline, template-disjoint split policy and one end-to-end invoice.
- **W3–4:** OCR/PDF baseline; implement both OCR-all and route-aware reading for controlled comparison; KIE header baseline; first line-item grouping; backend/frontend integration.
- **W5–6:** complete three input paths, normalization/checks, editable review and export; create independent mock-test templates not used by the generator.
- **W7–8:** error analysis, data/version QA, line-item hardening, freeze unseen-template and independent final test manifests; no more tuning on frozen final sets.
- **W9–10:** run final end-to-end benchmark, baseline/ablation matrix, robustness slices and latency measurements; optional small human-in-the-loop pilot if participants are available.
- **W11–12:** demo hardening, reproducibility, report, slides, video and release package with claims limited to the evaluated data.
- **W13–16 optional:** more templates/datasets, difficult tables, batch processing and an additional independent extension evaluation.

## Authoritative documents

- `docs/project-plan.md`
- `docs/research-design.md`
- `docs/dataset-strategy.md`
- `docs/architecture.md`
- `docs/integration-contracts.md`
- `docs/evaluation-plan.md`
- `schemas/invoice-kie-result.v2.schema.json` (target v2)
- `schemas/invoice-annotation.v2.schema.json` (target v2)
- `schemas/ocr-result.schema.json`

See `docs/migration-status.md` for the v1-runtime → v2-target transition. Historical Week-1/2/3 documents and closed issues may remain in Git history for traceability, but they are not current requirements.
