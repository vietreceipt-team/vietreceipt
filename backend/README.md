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
- `PROCESSING`
- `NEEDS_REVIEW`
- `VERIFIED`
- `FAILED`

Chuyển trạng thái hợp lệ được định nghĩa tại `../docs/receipt-state-machine.md`.

Backend tự động lên lịch xử lý sau khi upload thành công. `UPLOADED` nghĩa là ảnh và metadata đã commit; enqueue thành công vẫn giữ `UPLOADED`. Chỉ khi worker claim/start attempt thì receipt mới chuyển `PROCESSING`. Nếu scheduling/enqueue thất bại sau commit, receipt chuyển `FAILED` với `stage=SCHEDULING`, `retryable=true`. `QUEUED` chỉ là trạng thái nội bộ của queue, không phải trạng thái hóa đơn công khai; Frontend không gọi `/process`.

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
- Giữ nguyên `machine_needs_review` từ KIE và tính `effective_needs_review` sau correction/verification để Frontend hiển thị trạng thái hiện tại.
- Tính `effective_value` từ `corrected_value` khi có correction, nếu không dùng `normalized_value`; không fallback sang `predicted_value`.
- Correction history phải lưu cả thay đổi value và value status.
- API correction dùng canonical field name và một payload `APPLY`/`CLEAR`; correction và verify đều kiểm tra `expected_updated_at` để chống ghi đè thay đổi mới hơn.
- Chỉ dữ liệu `VERIFIED` được export chính thức theo mặc định.
- Mọi thay đổi contract phải cập nhật OpenAPI, JSON Schema, ví dụ và consumer test trong cùng Pull Request.


## Receipt persistence & application service (Backend-2 W2)

`app.services.ReceiptService` orchestrates image validation, safe object-key generation,
object storage, and receipt metadata persistence without depending on FastAPI, boto3,
filesystem paths, or SQL statements.

PostgreSQL metadata access is behind `ReceiptRepository`; the SQLAlchemy implementation
is `SQLAlchemyReceiptRepository`. Runtime database configuration has one source of truth:
`DATABASE_URL`.

Creation consistency strategy:

1. validate bytes and derive canonical content type/width/height;
2. store the image using a server-generated key;
3. insert receipt metadata;
4. if the database insert fails, attempt compensating object deletion;
5. if compensation also fails, log the failure and raise a typed application error.

Delete strategy is image-first, metadata-second. A missing object is treated as already
deleted. Storage unavailability stops metadata deletion. If metadata deletion fails after
image deletion, the inconsistency is logged and surfaced as `ReceiptDeleteFailure`.

Database schema changes are managed by Alembic. Production startup must not use
`Base.metadata.create_all()`.

From `backend/`:

```shell
python -m pip install -e ".[test]"
python -m pytest
alembic upgrade head
```


## Backend-2 receipt persistence integration

Backend-2 implements the concrete `ReceiptPersistenceService` port exposed by the
canonical Week-2 backend architecture. `ReceiptService` remains owned by the canonical
application layer; Backend-2 does not create a competing service.

Creation flow:

`ReceiptUpload -> content validation -> safe object key -> object storage -> canonical Receipt -> SQLAlchemy persistence`

If object storage succeeds but the database commit fails, the adapter attempts
compensating object deletion and raises canonical `PersistenceFailure`. A cleanup
failure is logged and remains observable.

`storage_key` and canonical storage `content_type` are persistence-internal metadata and
are not added to the public/domain `Receipt` model.

### Integration notes

Two contract gaps remain outside Backend-2 ownership:

1. `ReceiptUpload` currently carries no authenticated owner/user reference, so Backend-2
   cannot persist `user_id` without inventing a contract field.
2. The canonical `ReceiptService.upload_receipt()` wraps non-`PersistenceFailure`
   exceptions from the persistence port. That means validation/storage errors may be
   projected as `PersistenceFailure` at the API layer unless Backend Owner explicitly
   defines typed error propagation.

Backend-2 does not change those canonical contracts in this branch.
