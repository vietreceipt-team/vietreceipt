# TV5 — Backend & Integration V2

Theo Issue #50 và kế hoạch 19/09/2026. Nhánh dựa trên main `4f662e9e8cb4cbab309a8d187d318cba04945d6c`. Code cũ của W3 chưa merge không được đưa nguyên vào V2.

## Nhóm chức năng

- `/api/v1` giữ route/domain cũ. `/api/v2` dùng 13 trường hóa đơn, dòng hàng và nhóm thuế.
- Upload JPEG/PNG/PDF kiểm tra extension, MIME, dữ liệu thực, giới hạn 10 MiB, ảnh 40 triệu pixel, PDF 30 trang (khớp TV3 reader); PDF mã hóa bị từ chối. Filename chỉ là metadata, key được tạo từ UUID.
- Source lưu filesystem hoặc S3/MinIO qua abstraction hiện có. API và worker dùng cùng DATABASE_URL/storage. Không đưa source vào Git.
- Upload/retry ghi outbox cùng transaction. Beat dispatch mỗi 5 giây; job đã gửi nhưng chưa được worker claim sẽ được gửi lại sau 60 giây. Queue riêng `vietreceipt-v2` chỉ chứa receipt_id, tránh worker V1 nhận nhầm task.
- Worker claim bằng DB CAS và unique active receipt. Duplicate no-op. Lease 900 giây; hard task limit 870 giây. Reaper mỗi 60 giây đưa attempt hết lease sang FAILED retryable. Worker cũ bị fence, không ghi kết quả vào attempt mới.
- Mỗi attempt có attempt_id/ocr_run_id/kie_run_id mới. OCR có thể được lưu trước khi KIE thất bại. Machine runs không update/delete, có trigger DB và bảo vệ ORM.
- Projection có từng cell header/line/tax riêng, không lưu bảng dòng hàng thành một chuỗi JSON. Machine cell và human correction tách cột; audit giữ old/new value, actor demo-user và thời gian.
- Correction/verify dùng `expected_version` integer. Ghi đồng thời trả 409. Version này là cơ chế V2; không đổi expected_updated_at của V1.
- Verify yêu cầu đầy đủ 13 header và latest KIE run; mọi ô bị gắn cờ hoặc UNKNOWN/UNREADABLE/AMBIGUOUS cần review rõ ràng. Có thể xác nhận tình trạng không đọc được bằng correction có status tương ứng và value null; hệ thống không bịa giá trị.
- Export chỉ VERIFIED. JSON giữ header/items/taxes và metadata; CSV trả ZIP ba bảng liên kết receipt_id; XLSX gồm Invoices, Line Items, Tax Groups. XLSX giữ identifiers dạng text, không chạy formula. CSV giữ text gốc và escape formula prefix; khi mở CSV bằng Excel cần import cột identifier dạng Text để Excel không tự chuyển kiểu.

JSON có `value_statuses` và OCR/KIE run IDs; CSV/XLSX có cột `<field>_status` và tax_id. Vì vậy các giá trị null đã được người review xác nhận vẫn phân biệt UNKNOWN, UNREADABLE và NOT_PRESENT sau export.

## Cách chạy local

Python 3.12; từ thư mục gốc repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-ai.txt -r backend/requirements-dev.txt -r requirements-contracts.txt
mkdir -p .data
export DATABASE_URL=sqlite:///$PWD/.data/invoices.db
export CELERY_BROKER_URL=redis://localhost:6379/0
export STORAGE_FILESYSTEM_ROOT=$PWD/.data/sources
python -m alembic -c backend/alembic.ini upgrade head
python -m uvicorn backend.app.main:app --reload
```

Hai terminal khác, cùng biến môi trường:

```bash
python -m celery -A backend.app.v2.worker:celery_app worker --loglevel=info
python -m celery -A backend.app.v2.worker:celery_app beat --loglevel=info
```

SQLite phục vụ dev; nghiệm thu concurrency phải dùng PostgreSQL. Redis cần chạy trước worker/beat. API không tự tạo/drop bảng khi start.

## Compose riêng cho V2

```bash
docker compose -f docker-compose.v2.yml up --build
```

Stack gồm PostgreSQL, Redis, migration one-shot, API, worker và beat. Filesystem volume dùng chung giữa API/worker. API/migration/beat dùng image nhẹ; worker target cài đủ PaddleOCR/PDFium và thư viện CPU. Model cache có volume riêng. Provider mặc định dùng code thực của TV3/TV4 bên dưới; lần xử lý ảnh/scan đầu tiên cần mạng để tải model. Health/readiness chỉ xác nhận API và database, chưa chứng minh OCR/KIE thành công. Frontend chạy riêng theo `frontend/docs/frontend-v2.md`.

Trên Docker Desktop ARM64 đã xác minh PDF có lớp văn bản, nhưng Paddle trong Linux ARM64 bị SIGSEGV khi đọc ảnh/scan. Demo ảnh/scan trên macOS dùng worker Python 3.12 native với `--pool=solo --concurrency=1`; xem [báo cáo tích hợp](backend-v2-integration.md) để biết phạm vi kiểm thử và giới hạn runtime.

## Hợp đồng callable với TV3/TV4

```python
# TV3: bytes là source nguyên bản; identifier do backend cấp.
def process_document(data: bytes, *, content_type: str,
                     receipt_id: str, ocr_run_id: str) -> dict: ...

# TV4: kie_run_id là uuid.UUID; kết quả phải dùng đúng các ID nguồn.
def extract_invoice(evidence: dict, *, kie_run_id) -> dict: ...
```

```bash
export V2_DOCUMENT_READER_CALLABLE=ai.document_reader.backend:read_document
export V2_KIE_CALLABLE=ai.kie.v2:extract_invoice
```

Provider phải là callable đồng bộ; không quản lý transaction/lifecycle backend. Không đặt biến thì dùng hai provider mặc định ở trên. Cấu hình rỗng hoặc import lỗi trả PROVIDER_NOT_CONFIGURED, retryable; sửa cấu hình rồi retry có kiểm soát. Không tự fallback sang `ai.kie.pipeline.run_kie` vì hàm đó trả contract 1.3. ReaderError được giữ đúng code/retryable qua adapter có namespace `backend.app`.

Adapter ảnh có sẵn để opt-in: `backend.app.v2.providers:image_ocr_reader`; chỉ nhận JPEG/PNG, gọi `ai.ocr.run_ocr`, không tự xử lý PDF.

Evidence ảnh dùng `schemas/ocr-result.schema.json`. Đề xuất seam PDF nhiều trang để TV3/TV4 tích hợp:

```json
{
  "schema_version": "document-2.0",
  "receipt_id": "UUID",
  "ocr_run_id": "UUID",
  "pages": [
    {"page_index": 0, "evidence": {"schema_version": "1.3", "...": "OCRResult canonical đầy đủ"}}
  ]
}
```

Mỗi trang có cùng receipt/run ID; page_index liên tiếp từ 0, block IDs duy nhất toàn document (TV3 có thể prefix p0_, p1_). Mọi source_block_ids của KIE phải thuộc đúng evidence. Đây là seam backend hỗ trợ, cần TV3/TV4 xác nhận bằng integration thật. Backend không viết PDF text extraction/OCR/KIE thay hai thành viên đó.

KIE phải validate đúng `invoice-kie-result.v2.schema.json` và cross-record validator TV4: raw_text phải khớp evidence, source IDs theo thứ tự trang/reading order, metadata dòng tổng hợp đúng các ô. PRESENT có giá trị đúng kiểu/bằng chứng, non-PRESENT phải null; line_id duy nhất, dài tối đa 128 ký tự, theo pattern canonical của schema. Sai schema/provenance là FAILED không retryable, không publish NEEDS_REVIEW.

## API cho TV6

Xem `openapi/openapi-v2.yaml`, đồng bộ bằng:

```bash
PYTHONPATH=. python scripts/export_openapi_v2.py
```

| Method | Route sau /api/v2 | Nội dung |
|---|---|---|
| POST | /receipts | multipart file, optional source_group; 201 |
| GET | /receipts | limit/offset, summaries gồm invoice_number/currency và giá trị hiệu lực sau correction; query header theo batch |
| GET | /receipts/{id} | status/version, fields, line_items, tax_breakdown, source/evidence URLs |
| GET | /receipts/{id}/source | bytes JPEG/PNG/PDF |
| GET | /receipts/{id}/evidence | latest persisted OCR/evidence hoặc null |
| POST | /receipts/{id}/retry | expected_version; 202 |
| PATCH | /receipts/{id}/fields/{field}/correction | value, status, expected_version |
| PATCH | /receipts/{id}/line-items/{line_id}/{field}/correction | sửa một ô |
| PATCH | /receipts/{id}/tax-groups/{tax_id}/{field}/correction | sửa một ô |
| GET | /receipts/{id}/history | audit events |
| POST | /receipts/{id}/verify | expected_version |
| GET | /receipts/{id}/export?format=json\|csv\|xlsx | verified-only download |
| GET | /health | process health |
| GET | /readiness | database schema reachable |

Error trả code/message/request_id; không exception thô. User demo cố định, không giả định đã có auth production. Poll detail trong UPLOADED/PROCESSING; nhận version mới sau mỗi mutation.

## Kiểm thử và smoke

```bash
PYTHONPATH=.:backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest backend/tests -q
python tests/contracts/run_contract_tests.py
# DB riêng dùng cho test, đã migrate:
TEST_DATABASE_URL=postgresql+psycopg://... PYTHONPATH=.:backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest backend/tests/v2/test_postgres.py -q
# Khi API + Redis + worker + beat và provider thật đều sẵn sàng:
PYTHONPATH=. python infra/scripts/smoke-v2.py /path/to/invoice.png --database-url "$DATABASE_URL"
```

Smoke tự động xác nhận dữ liệu làm người review demo, kiểm tra đủ 13 header, verify và export 3 định dạng. Chỉ chạy với fixture cho phép; không tự xác nhận hóa đơn thật của người dùng. Chạy riêng ảnh, PDF text, PDF scan. Evidence chứa receipt/attempt/OCR/KIE IDs, số dòng, kích thước export, thời gian. Lưu API/worker/beat logs cùng evidence.

`--expected-json` kiểm tra header và số dòng/nhóm thuế với reference tổng hợp trước khi review. `--review-json` mô phỏng sửa tay bằng reference tổng hợp có header/line_items/tax_breakdown; artifact ghi riêng machine_header và reviewed_header, tuyệt đối không tính bản sửa là độ chính xác OCR. PDF text ghép từ thành spatial span theo baseline/khoảng cách, giữ khoảng trống giữa cột; ảnh/scan vẫn có lỗi OCR cần đối chiếu.

Workflow `backend-v2.yml` chạy PostgreSQL + Redis/Celery thật với provider TEST để kiểm tra plumbing; artifact có nhãn backend-test-providers, không được dùng làm bằng chứng OCR/KIE thật.

## Trạng thái nghiệm thu

Kết quả TV5 ban đầu được giữ trong `docs/tv5-verification.md`; cập nhật tích hợp sau khi TV3/TV4/TV6 đã merge xem `docs/backend-v2-integration.md`. Smoke trên hóa đơn tổng hợp không thay thế benchmark latency/failure trên fixture đã khóa, leader sign-off hoặc evaluation tuần 9–12.
