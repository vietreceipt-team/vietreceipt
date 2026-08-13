# Backend VietReceipt

## Receipt image storage (internal)

`app.storage` validates and persists receipt images for a future service layer; it does not change the public API. Pillow decodes actual content and accepts only JPEG, PNG, and WebP. Empty, corrupt, unsupported, or oversized content is rejected. The canonical upload-byte limit is configured with `MAX_UPLOAD_SIZE_BYTES` (default 10 MiB). Decoder safety is additionally bounded by the internal `MAX_IMAGE_PIXELS` limit; Pillow decompression-bomb warnings/errors are mapped to typed validation errors.

`ReceiptImageStorage` exposes `put`, `get`, and `delete`. The filesystem adapter supports local development/tests. The S3 adapter supports MinIO/S3-compatible storage and accepts an application-configured boto3 client, keeping SDK details outside business code.

Shared configuration follows the Backend Contract Owner convention: `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET` (default `vietreceipt`), `STORAGE_SECURE`, `MAX_UPLOAD_SIZE_BYTES`, and `ALLOWED_IMAGE_TYPES`. Backend-2 additionally owns development/internal settings `STORAGE_BACKEND`, `STORAGE_FILESYSTEM_ROOT`, `STORAGE_REGION`, and decoder-safety `MAX_IMAGE_PIXELS`. `ALLOWED_IMAGE_TYPES` must remain exactly JPEG/PNG/WebP so runtime configuration cannot create a second upload-format policy. Credentials must be supplied only at runtime.

Run from `backend/`:

```shell
python -m pip install -e ".[test]"
python -m pytest
```

Never log image bytes or credentials. Original filenames are not accepted by the key generator: keys use a receipt/generated UUID and an extension derived from validated content. Production buckets should be private, encrypted, and grant only minimum required permissions.

Thư mục này chứa mã nguồn backend và các API chính của hệ thống VietReceipt.

## Phạm vi chính

- Xác thực người dùng
- Quản lý tài khoản
- API tải hóa đơn lên hệ thống
- API lấy thông tin hóa đơn
- API xử lý hóa đơn
- API cập nhật các trường đã trích xuất
- API xác nhận hóa đơn
- API tìm kiếm và lọc hóa đơn
- API xuất dữ liệu
- Quản lý trạng thái xử lý hóa đơn
- Kết nối với OCR, KIE, cơ sở dữ liệu và lưu trữ tệp

## Thành viên phụ trách chính
Đỗ Xuân Nguyên-Đồng Sỹ Nguyên

## Trạng thái xử lý chính

- UPLOADED
- PROCESSING
- NEEDS_REVIEW
- VERIFIED
- FAILED

## Nguyên tắc

- Frontend không truy cập trực tiếp cơ sở dữ liệu.
- Các module OCR và KIE phải có giao diện dữ liệu rõ ràng.
- Không ghi khóa bí mật trực tiếp trong mã nguồn.
- Các thay đổi ảnh hưởng kiến trúc chung phải được trao đổi trước.
- Mọi thay đổi phải gắn với GitHub Issue tương ứng.
