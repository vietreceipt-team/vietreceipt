# VietReceipt Integration Contracts v1.3

Tài liệu này giải thích semantics giữa Backend, OCR, KIE và Frontend. Không sao chép lại full schema. Machine-readable sources of truth là:

- [`../schemas/ocr-result.schema.json`](../schemas/ocr-result.schema.json): OCR result.
- [`../schemas/kie-result.schema.json`](../schemas/kie-result.schema.json): KIE result.
- [`../openapi/openapi.yaml`](../openapi/openapi.yaml): Backend public API.

KIE field semantics lấy từ KIE Field Specification v1.1 trên branch `origin/docs/1-kie-field-spec`. Shared contract chỉ được coi là frozen sau sign-off của các owner liên quan.

## Canonical fields

Contract dùng đúng năm key, không dùng alias qua interface:

| Field | Canonical value khi `PRESENT` |
|---|---|
| `merchant_name` | JSON string, tên người bán/cửa hàng |
| `receipt_date` | JSON string `YYYY-MM-DD`, ngày giao dịch |
| `total_amount` | JSON integer không âm, đơn vị VND |
| `invoice_id` | JSON string; giữ số `0` đầu |
| `merchant_address` | JSON string, địa chỉ cửa hàng/chi nhánh |

`fields` là object có đúng năm key trên. Đây là quyết định v1.3, không còn TBD array/object.

## OCR run

Mỗi OCR result là một run bất biến có `ocr_run_id`, engine name/version, kích thước ảnh, duration, timestamp có timezone và các blocks. Re-run tạo ID mới; không sửa run cũ.

Mỗi block có `block_id`, nguyên văn `text`, `confidence`, `polygon` và `reading_order`. Polygon có bốn tọa độ normalized `[0,1]` theo thứ tự top-left, top-right, bottom-right, bottom-left trên ảnh sau EXIF orientation. `block_id` và `reading_order` duy nhất trong một run; reading order là integer zero-based. JSON Schema kiểm tra shape; service/database enforce uniqueness và immutability.

Backend không đưa local `image_path` vào public hoặc cross-service contract. Adapter OCR nhận opaque object reference, short-lived signed URL hoặc bytes qua interface nội bộ đã được owner thống nhất.

## KIE run và machine state

Mỗi KIE result là một run bất biến, liên kết đúng một `source_ocr_run_id`. Re-run tạo `kie_run_id` mới. Run lưu schema version, extractor name/version, duration và timestamp có timezone. `review_policy_version` được ghi khi policy versioned tạo review decision; normalization khác `null` phải có rule/version.

Mỗi field machine output giữ riêng:

- `raw_text`: nguyên văn source blocks ghép bằng `\n` theo `reading_order`;
- `predicted_value`: giá trị KIE chọn trước normalization;
- `normalized_value`: canonical value hoặc JSON `null`;
- `value_status`;
- `confidence`;
- `machine_needs_review` và `review_reasons`;
- `source_block_ids`.

Value statuses là `PRESENT`, `NOT_PRESENT`, `UNREADABLE`, `AMBIGUOUS`, `UNKNOWN`. Non-`PRESENT` luôn có normalized value `null`. `PRESENT` có predicted value và ít nhất một source block thuộc đúng source OCR run. Machine-created `NOT_PRESENT` và `UNREADABLE` vẫn cần human review. Không tìm được candidate mặc định là `UNKNOWN`, không tự suy thành `NOT_PRESENT`.

`machine_needs_review=true` yêu cầu ít nhất một reason code trong enum của KIE schema. Confidence nằm trong `[0,1]` nhưng không tự quyết định accept/reject; mọi số confidence trong example chỉ minh họa shape, không phải benchmark hay threshold.

## Correction và effective projection

Machine result không bị correction ghi đè. Backend tạo correction-history event append-only, gồm operation `APPLY` hoặc `CLEAR`, old/new status/value, authenticated actor và server timestamp.

Với active correction:

```text
effective_status = corrected_status
effective_value  = corrected_value nếu corrected_status = PRESENT, ngược lại null
```

Không có active correction:

```text
effective_status = value_status
effective_value  = normalized_value nếu value_status = PRESENT, ngược lại null
```

`effective_value` không fallback sang `predicted_value`. `machine_needs_review` là immutable provenance; Backend tính `effective_needs_review` cho UI hiện tại.

`APPLY` với status `PRESENT` yêu cầu corrected value đúng canonical type. Mọi non-`PRESENT` correction có corrected value `null`. `CLEAR` gỡ active correction nhưng vẫn append audit event.

## Authentication, ownership và concurrency

Mọi receipt endpoint yêu cầu authenticated user. Backend chỉ cho user truy cập receipt thuộc ownership của họ. Correction và verify ghi actor/timestamp.

Correction và verify dùng `expected_updated_at` có timezone làm optimistic-concurrency token. Token stale trả `409 Conflict`; Backend không silently overwrite state mới hơn.

## Receipt lifecycle và verification

Lifecycle giữ nguyên:

```text
UPLOADED -> PROCESSING -> NEEDS_REVIEW -> VERIFIED
                       \-> FAILED
FAILED -> PROCESSING khi Backend thực hiện retry policy
```

Upload thành công khiến Backend tự trigger processing; Frontend không gọi `/process`.

Verify chỉ thành công khi receipt đang `NEEDS_REVIEW`, có đủ năm effective fields, không còn `AMBIGUOUS`/`UNKNOWN`, mọi `PRESENT` value đúng canonical type, và mọi `NOT_PRESENT`/`UNREADABLE` đã được human xác nhận. Request phải dùng correction state mới nhất. Backend ghi verified actor và timestamp. Vi phạm trả `409 Conflict`.

## Upload và timestamps

Upload nhận `image/jpeg`, `image/png` hoặc `image/webp`, tối đa `10 MiB` (`10,485,760` bytes). Backend phải kiểm tra cả declared MIME type và nội dung file.

Mọi timestamp contract dùng RFC 3339/ISO 8601 có timezone, ví dụ `2026-08-12T03:00:00Z`.

## Owner sign-off còn cần

- OCR Owner: khả năng sản xuất/enforce polygon, coordinate convention, unique block/order và immutable runs.
- KIE Owner: machine-readable KIE schema mirror đúng v1.1, review policy và normalization metadata.
- Frontend Owner: object-shaped fields, effective projection, highlighting nhiều source blocks và error handling `401/403/409`.
- Backend Owner: persistence constraints, append-only audit, ownership enforcement, worker idempotency và transaction/concurrency implementation.
