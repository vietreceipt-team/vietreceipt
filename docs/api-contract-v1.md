# VietReceipt API Contract v1

Tài liệu này định nghĩa API contract ban đầu giữa Frontend và Backend
của VietReceipt.

## Base path

``` text
/api/v1
```

------------------------------------------------------------------------

## 1. Quy ước chung

### Content Type

-   API JSON: `application/json`
-   Upload ảnh: `multipart/form-data`

### JSON naming

Sử dụng `snake_case`.

### Receipt Status

`UPLOADED`, `PROCESSING`, `NEEDS_REVIEW`, `VERIFIED`, `FAILED`

### Core Fields v1

`store_name`, `date`, `total`, `invoice_id`, `address`

------------------------------------------------------------------------

## 2. Error Response

``` json
{
  "error": {
    "code": "RECEIPT_NOT_FOUND",
    "message": "Receipt not found"
  }
}
```

Ví dụ file không hợp lệ:

``` json
{
  "error": {
    "code": "INVALID_FILE_TYPE",
    "message": "Only supported receipt image formats are allowed"
  }
}
```

------------------------------------------------------------------------

## 3. Upload Receipt

### Endpoint

``` http
POST /api/v1/receipts
```

### Mục đích

Frontend upload ảnh hóa đơn lên Backend.

Backend: - validate file; - lưu file vào Storage; - tạo receipt; - gán
trạng thái ban đầu `UPLOADED`; - tự động trigger processing; - chuyển
sang `PROCESSING`; - điều phối OCR và KIE; - lưu kết quả xử lý; - trả về
`receipt_id`.

Frontend không cần gọi thêm endpoint `/process`.

### Request

`Content-Type: multipart/form-data`

Field: `file`

### Success Response

HTTP `201 Created`

``` json
{
  "receipt_id": "r001",
  "status": "PROCESSING",
  "created_at": "2026-08-10T15:00:00"
}
```

### Possible Errors

-   `400 INVALID_FILE`
-   `400 INVALID_FILE_TYPE`
-   `413 FILE_TOO_LARGE`
-   `500 INTERNAL_ERROR`

------------------------------------------------------------------------

## 4. Get Receipt

### Endpoint

``` http
GET /api/v1/receipts/{receipt_id}
```

### Mục đích

Frontend lấy trạng thái và dữ liệu hiện tại của receipt.

### Success Response

``` json
{
  "receipt_id": "r001",
  "status": "NEEDS_REVIEW",
  "fields": [
    {
      "field": "store_name",
      "raw_value": "WINMART",
      "normalized_value": "WINMART",
      "confidence": 0.97,
      "source_block_id": "block_1"
    },
    {
      "field": "date",
      "raw_value": "10/08/2026",
      "normalized_value": "2026-08-10",
      "confidence": 0.94,
      "source_block_id": "block_4"
    },
    {
      "field": "total",
      "raw_value": "325.000",
      "normalized_value": "325000",
      "confidence": 0.91,
      "source_block_id": "block_12"
    }
  ],
  "created_at": "2026-08-10T15:00:00",
  "updated_at": "2026-08-10T15:02:00"
}
```

### Possible Errors

-   `403 FORBIDDEN`
-   `404 RECEIPT_NOT_FOUND`
-   `500 INTERNAL_ERROR`

------------------------------------------------------------------------

## 5. Update Receipt Field

### Endpoint

``` http
PATCH /api/v1/receipts/{receipt_id}/fields/{field_name}
```

### Mục đích

Cho phép người dùng chỉnh sửa giá trị một field sau OCR/KIE.

### Request

``` json
{
  "value": "WinMart+"
}
```

### Success Response

``` json
{
  "receipt_id": "r001",
  "field": "store_name",
  "predicted_value": "WINMART",
  "corrected_value": "WinMart+"
}
```

Backend phải giữ giá trị dự đoán ban đầu, không overwrite raw
prediction.

### Possible Errors

-   `400 INVALID_FIELD`
-   `404 RECEIPT_NOT_FOUND`
-   `409 INVALID_RECEIPT_STATE`
-   `500 INTERNAL_ERROR`

------------------------------------------------------------------------

## 6. Verify Receipt

### Endpoint

``` http
POST /api/v1/receipts/{receipt_id}/verify
```

### Mục đích

Người dùng xác nhận receipt đã được kiểm tra.

State transition: `NEEDS_REVIEW -> VERIFIED`.

### Success Response

``` json
{
  "receipt_id": "r001",
  "status": "VERIFIED"
}
```

### Possible Errors

-   `404 RECEIPT_NOT_FOUND`
-   `409 INVALID_RECEIPT_STATE`
-   `500 INTERNAL_ERROR`

------------------------------------------------------------------------

## 7. Receipt Response Model

``` json
{
  "receipt_id": "r001",
  "status": "NEEDS_REVIEW",
  "fields": [],
  "created_at": "2026-08-10T15:00:00",
  "updated_at": "2026-08-10T15:02:00"
}
```

------------------------------------------------------------------------

## 8. Receipt Field Model

``` json
{
  "field": "total",
  "raw_value": "325.000",
  "normalized_value": "325000",
  "confidence": 0.91,
  "source_block_id": "block_12"
}
```

Field phải thuộc một trong: `store_name`, `date`, `total`, `invoice_id`,
`address`.

------------------------------------------------------------------------

## 9. Frontend Responsibilities

-   gửi file hóa đơn tới Backend;
-   không truy cập trực tiếp OCR, KIE hoặc Database;
-   hiển thị receipt status;
-   hiển thị dữ liệu OCR/KIE do Backend trả về;
-   cho phép người dùng chỉnh sửa field;
-   gọi verify sau khi người dùng xác nhận;
-   kiểm tra lại `GET /receipts/{receipt_id}` khi receipt đang
    `PROCESSING`.

------------------------------------------------------------------------

## 10. Backend Responsibilities

-   validate request;
-   tạo receipt;
-   quản lý receipt state;
-   lưu ảnh;
-   tự trigger processing sau khi upload;
-   điều phối OCR/KIE;
-   lưu kết quả dự đoán;
-   lưu giá trị chỉnh sửa;
-   xử lý lỗi;
-   kiểm soát truy cập;
-   trả response đúng contract.

------------------------------------------------------------------------

## 11. Main Frontend Flow

``` text
1. User chọn ảnh.
2. Frontend gọi POST /api/v1/receipts.
3. Backend lưu ảnh, tạo receipt và đặt UPLOADED.
4. Backend tự trigger processing và chuyển PROCESSING.
5. Backend chạy OCR -> KIE -> lưu kết quả.
6. Thành công -> NEEDS_REVIEW; lỗi -> FAILED.
7. Frontend dùng GET /api/v1/receipts/{receipt_id} để kiểm tra trạng thái.
8. NEEDS_REVIEW -> hiển thị field.
9. User sửa nếu cần -> PATCH field.
10. User xác nhận -> POST verify.
11. Receipt -> VERIFIED.
```

State flow:

``` text
UPLOAD
  |
  v
UPLOADED
  |
  | Backend tự trigger
  v
PROCESSING
  |        \
success     error
  |          |
  v          v
NEEDS_REVIEW FAILED
  |
  | user verify
  v
VERIFIED
```

------------------------------------------------------------------------

## 12. HTTP Status Codes

  HTTP status   Ý nghĩa
  ------------- -------------------------------------------
  200           Request thành công
  201           Tạo receipt thành công
  400           Request hoặc input không hợp lệ
  403           Không có quyền truy cập
  404           Không tìm thấy resource
  409           Trạng thái hiện tại không cho phép action
  413           File quá lớn
  500           Lỗi hệ thống

------------------------------------------------------------------------

## 13. API Version

Phiên bản hiện tại: `API Contract v1`

Base path: `/api/v1`

Nếu thay đổi phá vỡ request hoặc response schema, phải trao đổi với
Frontend và các module liên quan trước khi merge.

------------------------------------------------------------------------

## 14. Items cần xác nhận trước khi freeze API v1

-   [ ] `POST /receipts` dùng field upload tên `file`.
-   [ ] Response dùng `receipt_id`.
-   [ ] Frontend có cần `image_url` trong response hay không.
-   [x] Backend tự trigger processing sau khi upload thành công.
-   [ ] Frontend poll `GET /receipts/{id}` khi status là `PROCESSING`.
-   [ ] Format `fields` dùng array hay object.
-   [ ] Cách gửi corrected value.
-   [ ] Authentication chưa được đưa vào contract W1 hay cần đưa ngay.
-   [ ] Giới hạn kích thước file upload.
-   [ ] Loại file được chấp nhận.
