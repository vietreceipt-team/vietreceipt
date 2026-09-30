# Frontend Invoice V2 — TV6

## Kiểm kê và quyết định migration

| Quyết định | Mã hiện có | Cách xử lý |
| --- | --- | --- |
| KEEP | HTML shell, `assets/css/tailwind.css`, `assets/css/app.css`, fonts, `common.js` escape/format/status/navigation | Tái sử dụng trong các trang sản phẩm V2. |
| KEEP | `server.js` static route, `/api/v1/` proxy, W3 study modules và tests | Giữ pilot V1 chạy khi `FRONTEND_DATA_MODE=mock` được bật tường minh. |
| MIGRATE | `upload.js`, `receipts.js`, `receipt-detail.js`, `api.js` năm trường | Các trang ở API mode nạp module `*-v2.js` và `api-v2.js`; không render alias V1. |
| REMOVE khỏi UI V2 | Thanh tiến độ mẫu, năm tên field cũ, tên người dùng giả, form mật khẩu demo | V2 chỉ nhận response backend; `/login/` giải thích trạng thái auth. |
| ADD | `api-v2.js`, `source-v2.js`, ba module trang V2, PDF.js vendor, V2 contract/E2E tests | Upload, review từng ô, evidence nhiều trang, verify/export. |

## Contract dùng từ PR #53

- `POST /api/v2/receipts`: multipart `file`, optional `source_group`; response `InvoiceDetail` 201.
- `GET /api/v2/receipts?limit&offset`: `InvoicePage`; `GET /receipts/{id}` trả `version`, `fields`, `line_items`, `tax_breakdown`, source/evidence URLs và processing error.
- `PATCH /fields/{field}/correction`, `/line-items/{line_id}/{field}/correction`, `/tax-groups/{tax_id}/{field}/correction`: `{value,status,expected_version}`. Backend trả `InvoiceDetail` với version mới.
- `POST /retry`, `/verify`: `{expected_version}`; retry 202 trả `InvoiceDetail`; verify 200 trả `InvoiceDetail`.
- `GET /source`: JPEG/PNG/PDF bytes; `GET /evidence`: OCRResult 1.3 hoặc `document-2.0`; `GET /export?format=json|csv|xlsx`: JSON, ZIP CSV, XLSX.
- 409 chặn mutation. UI giữ bản soạn, yêu cầu người dùng tải phiên bản mới và xem lại trước khi lưu. Không tự tính totals hoặc tự xác nhận dữ liệu AI.

## Điểm chờ nghiệm thu

PR #53 hiện dùng test providers để chứng minh backend plumbing. Reader PDF/OCR TV3 và KIE V2 TV4 phải trả evidence/schema đúng, rồi cần chạy UI với backend thật cho ảnh, PDF text, PDF scan. Cần lưu trạng thái API/worker/beat, response, screenshot/video và export; test hiện tại của frontend chỉ là contract/provider test. Leader cần nghiệm thu trên dữ liệu cho phép. Issue #51 chưa nên đóng chỉ dựa trên UI và test provider.

Chạy backend V2 theo `docs/backend-v2.md` của PR #53 với PostgreSQL, Redis, Celery worker/beat và callable TV3/TV4. Chạy frontend API mode trỏ `BACKEND_API_ORIGIN` về backend, rồi kiểm tra:

1. Upload JPEG/PNG, PDF có text và PDF scan, xác minh 201 và kết quả worker thật.
2. Chờ `NEEDS_REVIEW` hoặc `FAILED`, kiểm tra source, trang PDF và block evidence.
3. Sửa header, line cell và tax cell; đối chiếu `expected_version` với response mới, thử cạnh tranh 409.
4. Verify chỉ khi backend chấp nhận; tải JSON, CSV ZIP và XLSX; kiểm tra nội dung file.
5. Ghi rõ provider, dataset/fixture, phiên bản PR và các giới hạn nếu TV3/TV4 chưa sẵn sàng.
