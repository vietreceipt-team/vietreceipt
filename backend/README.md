# Backend VietReceipt

Backend cung cấp REST API, quản lý vòng đời hóa đơn và điều phối pipeline OCR/KIE của VietReceipt.

## Phạm vi chính

- Xác thực và phân quyền người dùng.
- Upload, kiểm tra và quản lý ảnh hóa đơn.
- CRUD, tìm kiếm và lọc hóa đơn.
- Điều phối job preprocessing, OCR và KIE.
- Lưu OCR blocks, extracted fields và correction history.
- Cho phép sửa field và xác minh hóa đơn.
- Cung cấp dashboard và export dữ liệu đã xác minh.

## Kiến trúc v1

- Public API: FastAPI dưới prefix `/api/v1`.
- Tác vụ dài: worker bất đồng bộ; queue đề xuất Redis/Celery.
- Dữ liệu quan hệ: PostgreSQL.
- Ảnh: MinIO hoặc S3-compatible storage ở chế độ private.
- OCR/KIE: Python adapter tuân thủ schema trong `../schemas/`.
- Frontend chỉ gọi Backend API, không truy cập trực tiếp OCR, KIE, database hoặc storage.

## Trạng thái hóa đơn

- `UPLOADED`
- `QUEUED`
- `PROCESSING`
- `NEEDS_REVIEW`
- `VERIFIED`
- `FAILED`

Chuyển trạng thái hợp lệ được định nghĩa tại `../docs/receipt-state-machine.md`.

## Contract

- Public API: `../openapi/openapi.yaml`
- OCR/KIE integration: `../docs/integration-contracts.md`
- OCR schema: `../schemas/ocr-result.schema.json`
- KIE schema: `../schemas/kie-result.schema.json`

## Thành viên phụ trách chính

Đỗ Xuân Nguyên - Đồng Sỹ Nguyên

## Nguyên tắc

- Không ghi secret trực tiếp trong mã nguồn hoặc log.
- Mọi truy vấn receipt phải giới hạn theo người dùng được xác thực.
- Chuyển trạng thái phải đi qua một domain service chung.
- OCR/KIE không ghi trực tiếp vào database của Backend.
- Giữ riêng raw, predicted, normalized, corrected và effective value.
- Lưu OCR/KIE output bất biến theo `ocr_run_id` và `kie_run_id`; không ghi đè lần chạy cũ.
- Correction history phải lưu cả thay đổi value và value status.
- Chỉ dữ liệu `VERIFIED` được export chính thức theo mặc định.
- Mọi thay đổi contract phải cập nhật OpenAPI, JSON Schema, ví dụ và consumer test trong cùng Pull Request.
