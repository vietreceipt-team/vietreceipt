# VietReceipt API Contract v1

Machine-readable source of truth cho Backend public API là [`../openapi/openapi.yaml`](../openapi/openapi.yaml). File này chỉ là hướng dẫn tích hợp, không lặp full request/response schemas.

## Boundary

- Base path: `/api/v1`.
- Mọi receipt endpoint yêu cầu Bearer authentication.
- User chỉ truy cập receipt thuộc ownership của mình.
- JSON dùng `snake_case`.
- Timestamp có timezone.

## Endpoints

| Method | Path | Semantics |
|---|---|---|
| `POST` | `/receipts` | Upload JPEG/PNG/WebP tối đa 10 MiB; Backend tự trigger processing |
| `GET` | `/receipts/{receipt_id}` | Trả receipt và machine/correction/effective field projection |
| `PATCH` | `/receipts/{receipt_id}/fields/{field_name}` | Append correction event `APPLY`/`CLEAR`, có concurrency token |
| `POST` | `/receipts/{receipt_id}/verify` | Verify khi toàn bộ invariants đã được giải quyết |

Không có public endpoint `/process`.

Canonical field names là `merchant_name`, `receipt_date`, `total_amount`, `invoice_id`, `merchant_address`. `fields` được biểu diễn bằng object có đúng năm key này.

Correction và verify gửi `expected_updated_at`; stale state trả `409`. Correction/verification lưu authenticated actor và server timestamp. Chi tiết invariant, status, projection và error response xem OpenAPI cùng [`integration-contracts.md`](integration-contracts.md).
