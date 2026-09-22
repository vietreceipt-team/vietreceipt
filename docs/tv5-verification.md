# TV5 V2 — báo cáo kiểm thử và phụ thuộc

Ngày kiểm tra: 22/09/2026. Base của mã nguồn: `main` commit `4f662e9e8cb4cbab309a8d187d318cba04945d6c`.

## Đã chạy

| Nhóm | Lệnh | Kết quả |
| --- | --- | --- |
| Backend V1 và V2 | `PYTHONPATH=.:backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest backend/tests -q` | 156 passed, 1 skipped (PostgreSQL race); 1 warning từ Starlette TestClient |
| Shared OCR/KIE/evaluation | `PYTHONPATH=.:backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q` | 65 passed, 40 subtests passed |
| Contract legacy | `PYTHONPATH=. python tests/contracts/run_contract_tests.py` | toàn bộ kiểm tra báo PASS |
| OpenAPI V2 | `openapi_spec_validator.validate_spec` trên `openapi/openapi-v2.yaml` | hợp lệ |
| Migration SQLite | `backend/tests/v2/test_migrations.py` | upgrade, downgrade, upgrade; bảng legacy giữ nguyên; SQL UPDATE immutable run bị chặn |
| Lint/format | `ruff check --isolated --select E4,E7,E9,F,I` và `ruff format --check` trên module V2 | đạt sau khi format |

Review độc lập đã tái hiện và test đỏ trước khi sửa:
1. `line_id` có dấu `/` làm route correction trả 404; sửa route path converter, test `test_review_line_ids_with_slashes` xanh.
2. Ký tự không hợp lệ XML trong correction làm xuất XLSX lỗi 500; từ chối input không hợp lệ và test Unicode.
3. Provider trả `NaN` ở OCR/KIE vẫn qua JSON Schema, khiến serialization/DB fail; từ chối payload trước persistence và test OCR/KIE riêng.

## Đã thiết kế nhưng chưa chạy thật tại môi trường này

- `backend/tests/v2/test_postgres.py` yêu cầu `TEST_DATABASE_URL` dùng PostgreSQL đã migrate; hiện skip vì môi trường không có PostgreSQL service. CI mới có PostgreSQL service, cần xem log CI sau khi GitHub chấp nhận PR.
- `backend-v2.yml` có Redis/Celery/HTTP smoke với provider fake có nhãn `backend-test-providers`. Workflow chưa chạy trên GitHub, chưa khẳng định kết quả.
- Compose `docker-compose.v2.yml` chưa thể chạy do môi trường này không có Docker. Chưa có bằng chứng worker logs/receipt IDs của lượt E2E thật.
- Chưa có TV3 PDF-capable document reader và TV4 KIE callable trả schema V2 trên `main`; adapter V1.3 không dùng để đánh dấu success V2. Ảnh/PDF phải chạy smoke thật với provider của hai thành viên khi đã sẵn sàng.
- Frontend TV6 và acceptance với leader chưa thể kết luận từ backend tests.

## Những kết quả cần ghi sau CI và integration thật

- Xem `backend-v2` workflow: PostgreSQL migration/race, hợp đồng, Redis/Celery smoke PNG/PDF, artifact `image.json`, `pdf.json`, API/worker/beat logs.
- Chạy `infra/scripts/smoke-v2.py` với fixture được TV2 cho phép và callable thật TV3/TV4. Chụp `receipt_id`, `attempt_id`, `ocr_run_id`, `kie_run_id`, 13 header, line/tax counts, trạng thái xác nhận, kích thước ba export.
- Kiểm tra riêng ảnh, PDF text, PDF scan; UI sửa từng ô và tải export theo OpenAPI V2.

Issue #50 cần giữ Open đến khi đầy đủ các bước trên, có người review và nhóm chấp nhận kết quả.
