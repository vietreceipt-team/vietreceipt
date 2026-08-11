# VietReceipt Integration Conventions v1

Tài liệu này định nghĩa các quy ước tích hợp chung giữa Frontend, Backend, OCR, KIE, Database và Storage của VietReceipt.

Mục tiêu là đảm bảo các module sử dụng cùng cách đặt tên, cùng format dữ liệu và cùng cách xử lý trạng thái để tránh lỗi khi tích hợp.

---

## 1. API Version

Tất cả API Backend trong phiên bản đầu sử dụng prefix:

```text
/api/v1
```

Các API chính:

```text
POST  /api/v1/receipts
GET   /api/v1/receipts/{receipt_id}
PATCH /api/v1/receipts/{receipt_id}/fields/{field_name}
POST  /api/v1/receipts/{receipt_id}/verify
```

Nếu sau này có breaking change lớn, phải tạo version mới thay vì âm thầm thay đổi contract cũ.

Ví dụ:

```text
/api/v2
```

---

## 2. JSON Naming Convention

Tất cả field JSON sử dụng:

```text
snake_case
```

Ví dụ đúng:

```text
receipt_id
store_name
normalized_value
source_block_id
created_at
updated_at
```

Không sử dụng lẫn các kiểu như:

```text
receiptId
StoreName
normalized-value
sourceBlockID
```

---

## 3. Core Fields v1

Phiên bản đầu của VietReceipt tập trung vào 5 field:

```text
store_name
date
total
invoice_id
address
```

| Field key | Ý nghĩa |
|---|---|
| `store_name` | Tên cửa hàng |
| `date` | Ngày trên hóa đơn |
| `total` | Tổng tiền |
| `invoice_id` | Mã hóa đơn |
| `address` | Địa chỉ |

Không tự ý đổi tên hoặc thêm field mới nếu chưa cập nhật contract chung.

---

## 4. Receipt Status

Các trạng thái receipt:

```text
UPLOADED
PROCESSING
NEEDS_REVIEW
VERIFIED
FAILED
```

### UPLOADED

Ảnh hóa đơn đã được Backend nhận và lưu thành công.

### PROCESSING

Receipt đang được Backend điều phối qua OCR và KIE.

### NEEDS_REVIEW

OCR/KIE đã có kết quả và cần người dùng kiểm tra hoặc chỉnh sửa.

### VERIFIED

Người dùng đã kiểm tra và xác nhận dữ liệu receipt.

### FAILED

Quá trình xử lý receipt gặp lỗi.

Luồng trạng thái chính:

```text
UPLOADED
    |
    v
PROCESSING
    |       \
    |        \
    v         v
NEEDS_REVIEW FAILED
    |
    v
VERIFIED
```

Không tự tạo thêm status ngoài contract nếu chưa được thống nhất.

---

## 5. Processing Convention

Sau khi Frontend upload receipt thành công:

```text
POST /api/v1/receipts
```

Backend tự động trigger processing.

Frontend không cần gọi endpoint `/process`.

Luồng:

```text
Frontend
    |
    | POST /api/v1/receipts
    v
Backend
    |
    v
UPLOADED
    |
    | Backend tự trigger
    v
PROCESSING
    |
    v
OCR
    |
    v
KIE
    |
    v
NEEDS_REVIEW
```

Frontend sử dụng:

```text
GET /api/v1/receipts/{receipt_id}
```

để kiểm tra trạng thái và lấy kết quả xử lý.

---

## 6. OCR Output Convention

Theo scope hiện tại, OCR phải trả tối thiểu:

- nội dung văn bản;
- độ tin cậy;
- bounding box.

Schema đề xuất:

```json
{
  "block_id": "block_1",
  "text": "WINMART",
  "confidence": 0.98,
  "bbox": [20, 30, 150, 60],
  "order": 1
}
```

### block_id

Định danh của OCR block trong một receipt.

Ví dụ:

```text
block_1
block_2
block_3
```

### text

Nội dung OCR nhận dạng được.

Ví dụ:

```text
WINMART
```

### confidence

Độ tin cậy OCR.

Format đề xuất:

```text
0.0 -> 1.0
```

Ví dụ:

```text
0.98
```

### bbox

Bounding box đề xuất:

```text
[x1, y1, x2, y2]
```

Ví dụ:

```json
[20, 30, 150, 60]
```

### order

Thứ tự đọc của OCR block.

Ví dụ:

```text
1
2
3
```

`block_id`, `order` và format chính xác của `bbox` cần được OCR và KIE xác nhận trước khi freeze contract.

---

## 7. KIE Input Convention

KIE nhận OCR blocks đã được chuẩn hóa.

Ví dụ:

```json
{
  "receipt_id": "r001",
  "blocks": [
    {
      "block_id": "block_1",
      "text": "WINMART",
      "confidence": 0.98,
      "bbox": [20, 30, 150, 60],
      "order": 1
    }
  ]
}
```

KIE cần nhận được:

- OCR text;
- bounding box;
- OCR confidence;
- thứ tự và vị trí các vùng văn bản.

KIE không nên phụ thuộc cứng vào output riêng của một OCR engine cụ thể.

---

## 8. KIE Output Convention

Mỗi field KIE trả về phải có tối thiểu:

```text
field
raw_value
normalized_value
confidence
source_block_id
```

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

### field

Phải thuộc một trong 5 core field:

```text
store_name
date
total
invoice_id
address
```

### raw_value

Giá trị gốc được trích xuất từ kết quả OCR.

Ví dụ:

```text
325.000
```

### normalized_value

Giá trị sau khi KIE chuẩn hóa.

Ví dụ:

```text
325000
```

### confidence

Độ tin cậy của KIE.

Format:

```text
0.0 -> 1.0
```

### source_block_id

Tham chiếu tới OCR block liên quan.

Ví dụ:

```text
block_12
```

---

## 9. Date Convention

Ngày sau khi normalize đề xuất sử dụng:

```text
YYYY-MM-DD
```

Ví dụ OCR/KIE đọc:

```text
10/08/2026
```

Kết quả:

```json
{
  "raw_value": "10/08/2026",
  "normalized_value": "2026-08-10"
}
```

Format này cần được Backend và KIE xác nhận trước khi freeze contract.

---

## 10. Total Convention

Giá trị tổng tiền phải tách rõ:

```text
raw_value
normalized_value
```

Ví dụ:

```json
{
  "raw_value": "325.000",
  "normalized_value": "325000"
}
```

Không tự thêm ký hiệu tiền tệ vào `normalized_value` nếu contract chưa định nghĩa field tiền tệ riêng.

---

## 11. Confidence Convention

OCR confidence và KIE confidence đề xuất thống nhất dưới dạng:

```text
float
0.0 -> 1.0
```

Ví dụ:

```text
0.91
0.98
0.75
```

Không dùng lẫn nhiều format như:

```text
91
98%
0.91
```

---

## 12. Datetime Convention

Các timestamp hệ thống như:

```text
created_at
updated_at
```

sử dụng ISO 8601.

Ví dụ:

```text
2026-08-10T15:00:00
```

Timezone cụ thể cần được Backend và Database thống nhất trước khi production.

---

## 13. Error Convention

Backend sử dụng error response chung:

```json
{
  "error": {
    "code": "RECEIPT_NOT_FOUND",
    "message": "Receipt not found"
  }
}
```

`error.code` sử dụng:

```text
UPPER_SNAKE_CASE
```

Ví dụ:

```text
RECEIPT_NOT_FOUND
INVALID_FILE
INVALID_FILE_TYPE
INVALID_RECEIPT_STATE
INTERNAL_ERROR
```

Frontend nên dựa vào `error.code` để xử lý logic.

---

## 14. File Upload Convention

Upload receipt sử dụng:

```text
multipart/form-data
```

Field upload:

```text
file
```

Ví dụ:

```text
file = receipt.jpg
```

Giới hạn kích thước file và các loại file được hỗ trợ cần được Backend và Frontend xác nhận trước khi freeze API v1.

---

## 15. Storage Convention

Frontend không truy cập trực tiếp Storage nội bộ.

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
- quản lý đường dẫn hoặc object key;
- kiểm soát quyền truy cập;
- không trả filesystem path nội bộ cho Frontend nếu không cần thiết.

Nếu Frontend cần xem lại ảnh receipt, Backend phải cung cấp URL hoặc endpoint phù hợp.

---

## 16. Database Convention

Frontend không truy cập trực tiếp Database.

OCR và KIE cũng không tự ghi trực tiếp vào Database chính của hệ thống nếu chưa có contract riêng.

Luồng:

```text
OCR / KIE
    |
    v
Backend
    |
    v
Database
```

Backend chịu trách nhiệm quản lý dữ liệu nghiệp vụ và receipt lifecycle.

---

## 17. Raw Prediction Convention

Hệ thống phải giữ lại prediction ban đầu trước khi người dùng chỉnh sửa.

Ví dụ:

```text
predicted_value = WINMART
corrected_value = WinMart+
```

Không overwrite prediction ban đầu làm mất dữ liệu dự đoán.

Việc giữ raw prediction phục vụ:

- correction history;
- audit;
- đánh giá OCR/KIE;
- cải thiện model sau này.

---

## 18. Module Communication Rules

### Frontend -> Backend

Giao tiếp qua REST API.

```text
Frontend
    |
    | REST API
    v
Backend
```

### Backend -> OCR

Backend gửi ảnh hoặc image reference thông qua interface/service được thống nhất.

```text
Backend
    |
    | image / image reference
    v
OCR
```

### OCR -> KIE

Dùng OCR block schema chuẩn.

```text
OCR
    |
    | blocks[]
    v
KIE
```

### KIE -> Backend

KIE trả structured fields.

```text
KIE
    |
    | fields[]
    v
Backend
```

### Backend -> Database

Backend chịu trách nhiệm ghi và đọc dữ liệu nghiệp vụ.

```text
Backend
    |
    v
Database
```

### Backend -> Storage

Backend quản lý việc lưu và truy xuất ảnh.

```text
Backend
    |
    v
Storage
```

Không để module phụ thuộc trực tiếp vào implementation nội bộ của module khác nếu có thể tránh.

---

## 19. Encoding

Source code, JSON và tài liệu sử dụng:

```text
UTF-8
```

---

## 20. Breaking Changes

Các thay đổi sau được coi là breaking change:

- đổi tên field;
- đổi kiểu dữ liệu;
- đổi format bbox;
- đổi confidence scale;
- đổi receipt status;
- đổi OCR output schema;
- đổi KIE input/output schema;
- đổi URL API;
- đổi request/response schema;
- xóa field đang được module khác sử dụng.

Breaking change phải được trao đổi với các module liên quan trước khi merge.

---

## 21. Items cần xác nhận trước khi freeze Integration Conventions v1

- [ ] 5 field key được toàn nhóm xác nhận.
- [ ] OCR có `block_id`.
- [ ] OCR có `order`.
- [ ] bbox dùng `[x1, y1, x2, y2]`.
- [ ] confidence dùng `0.0 -> 1.0`.
- [ ] KIE dùng `source_block_id`.
- [ ] date normalize thành `YYYY-MM-DD`.
- [ ] total normalize theo format thống nhất.
- [x] Backend tự trigger processing sau upload.
- [ ] Frontend dùng polling khi receipt đang `PROCESSING`.
- [ ] Giới hạn kích thước file upload.
- [ ] Các loại ảnh được Backend chấp nhận.
- [ ] Cách Frontend truy cập ảnh receipt nếu cần.