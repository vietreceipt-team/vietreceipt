# Kiến trúc hệ thống VietReceipt

Tài liệu này mô tả kiến trúc tổng thể và cách các module chính của VietReceipt giao tiếp với nhau.

---

## 1. Mục tiêu kiến trúc

VietReceipt xử lý ảnh hóa đơn và chuyển thành dữ liệu có cấu trúc để người dùng có thể kiểm tra, chỉnh sửa, lưu trữ, tìm kiếm và xuất dữ liệu.

Các module chính:

- Frontend
- Backend
- OCR
- KIE
- Database
- File Storage
- DevOps / QA

Backend là module trung tâm chịu trách nhiệm điều phối luồng xử lý giữa Frontend, OCR, KIE, Database và Storage.

---

## 2. Kiến trúc tổng thể

```text
User
  |
  v
Frontend
  |
  | REST API
  v
Backend - FastAPI
  |
  +------------------> Storage
  |
  +------------------> Database
  |
  | image / image reference
  v
OCR
  |
  | OCR blocks
  v
KIE
  |
  | structured fields
  v
Backend
  |
  v
Database
  |
  v
Backend
  |
  v
Frontend
```

Frontend không truy cập trực tiếp OCR, KIE hoặc Database.

---

## 3. Luồng xử lý chính

Luồng xử lý một hóa đơn:

```text
Ảnh hóa đơn
    |
    v
Frontend
    |
    | POST /api/v1/receipts
    v
Backend
    |
    +--> Validate file
    |
    +--> Lưu ảnh vào Storage
    |
    +--> Tạo receipt trong Database
    |
    v
UPLOADED
    |
    | Backend tự trigger processing
    v
PROCESSING
    |
    v
OCR
    |
    | text + confidence + bbox
    v
KIE
    |
    | structured fields
    v
Backend
    |
    +--> Lưu OCR result
    |
    +--> Lưu KIE result
    |
    v
NEEDS_REVIEW
    |
    v
Frontend
    |
    | User kiểm tra / chỉnh sửa
    v
VERIFIED
```

Nếu processing gặp lỗi:

```text
PROCESSING
    |
    v
FAILED
```

---

## 4. Frontend -> Backend

Frontend giao tiếp với Backend thông qua REST API.

Base path:

```text
/api/v1
```

Các API core v1:

```text
POST  /api/v1/receipts
GET   /api/v1/receipts/{receipt_id}
PATCH /api/v1/receipts/{receipt_id}/fields/{field_name}
POST  /api/v1/receipts/{receipt_id}/verify
```

Frontend chịu trách nhiệm:

- upload ảnh hóa đơn;
- hiển thị trạng thái receipt;
- lấy kết quả OCR/KIE thông qua Backend;
- cho phép người dùng chỉnh sửa field;
- gửi yêu cầu verify.

Frontend không gọi trực tiếp OCR hoặc KIE.

---

## 5. Backend -> OCR

Backend gửi ảnh hóa đơn hoặc image reference cho OCR.

Luồng:

```text
Backend
   |
   | image / image reference
   v
OCR
```

OCR chịu trách nhiệm:

- tiền xử lý ảnh;
- chạy OCR;
- nhận dạng text;
- trả confidence;
- trả bounding box.

OCR output được chuẩn hóa thành các OCR block.

Ví dụ:

```json
{
  "block_id": "block_1",
  "text": "WINMART",
  "confidence": 0.98,
  "bbox": [20, 30, 150, 60],
  "order": 1
}
```

Chi tiết schema được định nghĩa trong:

```text
docs/integration-schema.md
```

---

## 6. OCR -> KIE

KIE nhận OCR blocks đã chuẩn hóa.

Luồng:

```text
OCR
   |
   | blocks[]
   v
KIE
```

KIE sử dụng:

- OCR text;
- bounding box;
- OCR confidence;
- thứ tự / vị trí OCR blocks.

KIE chịu trách nhiệm trích xuất 5 field chính của VietReceipt.

---

## 7. KIE -> Backend

KIE trả structured fields cho Backend.

Ví dụ:

```json
{
  "field": "total",
  "raw_value": "325.000",
  "normalized_value": "325000",
  "confidence": 0.91,
  "source_block_id": "block_12"
}
```

Backend chịu trách nhiệm lưu prediction trước khi người dùng chỉnh sửa.

---

## 8. Backend -> Database

Backend là module chịu trách nhiệm chính khi đọc và ghi dữ liệu nghiệp vụ.

Luồng:

```text
Backend
   |
   v
Database
```

Database cần lưu tối thiểu:

- receipt;
- receipt status;
- OCR result;
- KIE prediction;
- normalized value;
- corrected value;
- correction history;
- timestamps.

Frontend, OCR và KIE không truy cập trực tiếp Database chính nếu chưa có contract riêng.

---

## 9. Backend -> Storage

Ảnh hóa đơn được lưu thông qua Backend.

Luồng:

```text
Frontend
   |
   v
Backend
   |
   v
Storage
```

Backend chịu trách nhiệm:

- lưu ảnh;
- quản lý image reference;
- kiểm soát truy cập;
- cung cấp URL hoặc endpoint phù hợp nếu Frontend cần xem lại ảnh.

Frontend không sử dụng filesystem path nội bộ.

---

## 10. Các trường thông tin chính

VietReceipt v1 tập trung vào 5 trường:

| Tên hiển thị | Field key |
|---|---|
| Tên cửa hàng | store_name |
| Ngày | date |
| Tổng tiền | total |
| Mã hóa đơn | invoice_id |
| Địa chỉ | address |

Tên field phải thống nhất giữa Frontend, Backend, KIE và Database.

---

## 11. Receipt State Machine

Các trạng thái:

```text
UPLOADED
PROCESSING
NEEDS_REVIEW
VERIFIED
FAILED
```

Luồng:

```text
UPLOADED
    |
    | Backend tự trigger
    v
PROCESSING
    |       \
    |        \
success      error
    |          |
    v          v
NEEDS_REVIEW FAILED
    |
    | user verify
    v
VERIFIED
```

Ý nghĩa:

### UPLOADED

Ảnh hóa đơn đã được Backend nhận và lưu.

### PROCESSING

Backend đang điều phối OCR và KIE.

### NEEDS_REVIEW

OCR/KIE đã có kết quả và dữ liệu cần được người dùng kiểm tra.

### VERIFIED

Người dùng đã xác nhận dữ liệu.

### FAILED

Processing gặp lỗi.

---

## 12. Backend Processing Responsibility

Sau khi Frontend gọi:

```text
POST /api/v1/receipts
```

Backend tự trigger processing.

Frontend không cần gọi endpoint:

```text
/process
```

Backend chịu trách nhiệm:

```text
Upload
  ->
UPLOADED
  ->
PROCESSING
  ->
OCR
  ->
KIE
  ->
Database
  ->
NEEDS_REVIEW
```

---

## 13. Nguyên tắc kiến trúc

- OCR không được giả định là luôn chính xác.
- Người dùng phải có khả năng chỉnh sửa kết quả.
- Hệ thống phải giữ prediction trước khi người dùng chỉnh sửa.
- Frontend không truy cập trực tiếp Database.
- Frontend không gọi trực tiếp OCR/KIE.
- OCR và KIE phải giao tiếp thông qua schema rõ ràng.
- Backend chịu trách nhiệm orchestration.
- Không hard-code secrets trong source code.
- Không để core flow phụ thuộc vào script chỉ chạy local.
- Thay đổi breaking contract phải được trao đổi với các module liên quan trước khi merge.

---

## 14. Tài liệu contract liên quan

Architecture phải được đọc cùng các tài liệu:

```text
docs/api-contract-v1.md
docs/integration-schema.md
docs/integration-conventions.md
```

Trong đó:

- `api-contract-v1.md`: Frontend <-> Backend.
- `integration-schema.md`: Backend / OCR / KIE schema.
- `integration-conventions.md`: quy ước chung giữa các module.