# Đánh giá tích hợp Backend VietReceipt

Đối chiếu ngày 22/08/2026 với GitHub `vietreceipt-team/vietreceipt`:

- `origin/main`: `e534de2f9afa1d56a60b2bf835808f65206bf2a5`
- contract branch `docs/2-week1-backend-contract`: `f1eaed210144140184388cdb84d71c1d79493e13`
- KIE field spec branch: `391b9b981dae4e3b55dc7266de43be997b0ba274`

## Kết luận

Chuyển frontend thành HTML/CSS/JavaScript thuần là hợp lý. Backend là REST/JSON FastAPI nên không phụ thuộc React hoặc TypeScript. Điều quyết định khả năng kết nối là giữ một integration boundary, model đúng contract, same-origin proxy và cơ chế concurrency; bản này đã chuẩn bị bốn phần đó.

## Những điểm đã sửa so với frontend TypeScript cũ

1. Public receipt states chỉ còn `UPLOADED`, `PROCESSING`, `NEEDS_REVIEW`, `VERIFIED`, `FAILED`; `QUEUED` là trạng thái queue nội bộ.
2. Upload `POST /api/v1/receipts` tự động schedule. Frontend không gọi `/process`.
3. `ReceiptDetail.fields` là object có đúng năm canonical keys, không phải array.
4. Field dùng `field_name`; correction không dùng `field_id` công khai.
5. Correction gọi `PATCH /api/v1/receipts/{receipt_id}/fields/{field_name}/correction` với payload phân biệt `operation: "APPLY" | "CLEAR"`.
6. `APPLY` gửi `field.updated_at` trong `expected_updated_at`; HTTP 409 không được tự retry.
7. Sau correction, frontend tải lại ReceiptDetail để nhận `receipt.updated_at` mới rồi mới verify.
8. Verify gọi `POST /api/v1/receipts/{receipt_id}/verify` với `expected_updated_at: receipt.updated_at`.
9. Retry HTTP 202 chỉ nghĩa là schedule đã được chấp nhận; UI tải lại receipt và không tự gán `PROCESSING`.
10. Ảnh dùng `image_url` do ReceiptDetail trả; frontend không tự dựng storage URL.

## Endpoint runtime hiện có trên `origin/main`

- `POST /api/v1/receipts`
- `GET /api/v1/receipts`
- `GET /api/v1/receipts/{receipt_id}`
- `POST /api/v1/receipts/{receipt_id}/retry`
- `GET /api/v1/receipts/{receipt_id}/fields`
- `PATCH /api/v1/receipts/{receipt_id}/fields/{field_name}/correction`
- `POST /api/v1/receipts/{receipt_id}/verify`
- `GET /api/v1/receipts/{receipt_id}/history`

OpenAPI còn mô tả auth, delete, image, OCR, dashboard và export, nhưng runtime router hiện chưa có đầy đủ các route này. Không nên nối UI production vào route chỉ có trong YAML cho tới khi runtime và contract tests cùng xác nhận.

## Blocker phía Backend trước khi kết nối thật

- `backend.app.main:create_app()` mặc định đặt `service_registry = None`; nhiều endpoint sẽ trả 500 cho tới khi repository/persistence/services thật được wire.
- Backend chưa cài `CORSMiddleware`. Với frontend và backend khác origin, browser sẽ bị chặn nếu chưa thêm CORS/cookie policy. Khuyến nghị deploy cùng origin và reverse proxy `/api/v1/*`.
- Runtime router chưa có auth mặc dù OpenAPI có `/auth/login` và `/auth/register`; trang login hiện tiếp tục là demo cục bộ.
- Cần xác nhận `image_url` là URL có quyền truy cập phù hợp và thời hạn đủ cho phiên review.
- List response không có `image_url`; thumbnail danh sách hiện dùng fallback, đúng với response model runtime.

## Thứ tự nối thật đề xuất

1. Backend wire `ServiceRegistry` với persistence/repository thật và chạy route tests.
2. Đặt reverse proxy cùng origin cho `/api/v1` hoặc thêm CORS/cookie policy rõ ràng.
3. Đổi `assets/js/config.js` sang `dataMode: "api"`.
4. Test upload → polling UPLOADED/PROCESSING → NEEDS_REVIEW → APPLY correction → refetch → verify.
5. Test riêng HTTP 409 stale write, 413 file quá lớn, 415 sai MIME, 422 sai canonical type và FAILED retry.
6. Chỉ sau khi auth runtime được merge mới thay trang đăng nhập demo bằng request thật.
