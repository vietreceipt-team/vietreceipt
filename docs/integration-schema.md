# VietReceipt Integration Schema v1

Tài liệu này định nghĩa schema dữ liệu chung giữa Backend, OCR và KIE của hệ thống VietReceipt.

## 1. Core Fields

Phiên bản v1 tập trung vào 5 trường thông tin chính:

| Tên hiển thị | Field key |
|---|---|
| Tên cửa hàng | store_name |
| Ngày | date |
| Tổng tiền | total |
| Mã hóa đơn | invoice_id |
| Địa chỉ | address |

> Các `field key` trên là quy ước đề xuất cho contract v1 và cần được các thành viên liên quan xác nhận trước khi coi là contract chính thức.

---

## 2. Luồng dữ liệu chung

```text
Frontend
    |
    | upload image
    v
Backend
    |
    +------> Storage
    |
    | image / image reference
    v
OCR
    |
    | OCR blocks
    v
KIE
    |
    | extracted fields
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

Backend chịu trách nhiệm điều phối luồng xử lý giữa các module.

---

## 3. Backend -> OCR

### Input

OCR nhận ảnh hóa đơn hoặc tham chiếu tới ảnh hóa đơn.

Schema đề xuất:

```json
{
  "receipt_id": "r001",
  "image_path": "/storage/receipts/r001.jpg"
}
```

Trong đó:

- `receipt_id`: ID của hóa đơn do Backend quản lý.
- `image_path`: đường dẫn hoặc tham chiếu tới ảnh hóa đơn.

Cách truyền ảnh thực tế giữa Backend và OCR cần được Backend và thành viên OCR thống nhất trước khi triển khai.

---

## 4. OCR Output

Theo yêu cầu hiện tại của module OCR, mỗi vùng OCR phải có tối thiểu:

- Nội dung văn bản.
- Độ tin cậy.
- Bounding box.

Để KIE có thể tham chiếu tới vùng OCR và xác định thứ tự đọc, schema v1 đề xuất:

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
    },
    {
      "block_id": "block_2",
      "text": "TONG TIEN 325.000",
      "confidence": 0.95,
      "bbox": [20, 300, 220, 330],
      "order": 2
    }
  ]
}
```

### Quy ước OCR Block

- `block_id`: định danh của vùng OCR trong một receipt.
- `text`: nội dung văn bản OCR nhận dạng được.
- `confidence`: độ tin cậy của OCR.
- `bbox`: tọa độ bounding box.
- `order`: thứ tự đọc của vùng văn bản.

### Quy ước đề xuất

```text
confidence: 0.0 -> 1.0

bbox:
[x1, y1, x2, y2]
```

`block_id`, `order` và format chính xác của `bbox` cần được thành viên OCR và KIE xác nhận trước khi contract được freeze.

---

## 5. OCR -> KIE

KIE nhận dữ liệu OCR đã được chuẩn hóa.

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
    },
    {
      "block_id": "block_2",
      "text": "TONG TIEN 325.000",
      "confidence": 0.95,
      "bbox": [20, 300, 220, 330],
      "order": 2
    }
  ]
}
```

Theo yêu cầu hiện tại của KIE, input phải cung cấp:

- Văn bản OCR.
- Bounding box.
- Độ tin cậy OCR.
- Thứ tự và vị trí các vùng văn bản.

---

## 6. KIE Output

KIE trả về các trường thông tin đã trích xuất.

Mỗi trường cần có:

- Loại trường.
- Giá trị gốc.
- Giá trị đã chuẩn hóa.
- Độ tin cậy.
- Tham chiếu tới vùng OCR liên quan.

Schema:

```json
{
  "receipt_id": "r001",
  "fields": [
    {
      "field": "store_name",
      "raw_value": "WINMART",
      "normalized_value": "WINMART",
      "confidence": 0.97,
      "source_block_id": "block_1"
    },
    {
      "field": "total",
      "raw_value": "325.000",
      "normalized_value": "325000",
      "confidence": 0.91,
      "source_block_id": "block_2"
    }
  ]
}
```

---

## 7. Field Keys

KIE chỉ trả về các field thuộc scope v1:

```text
store_name
date
total
invoice_id
address
```

Ý nghĩa:

| Field | Ý nghĩa |
|---|---|
| store_name | Tên cửa hàng |
| date | Ngày trên hóa đơn |
| total | Tổng tiền |
| invoice_id | Mã hóa đơn |
| address | Địa chỉ |

Không tự tạo thêm hoặc đổi tên field nếu chưa cập nhật contract chung.

---

## 8. Raw và Normalized Value

KIE phải giữ cả giá trị gốc và giá trị đã chuẩn hóa.

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

Trong đó:

```text
raw_value
= kết quả gốc được trích xuất.

normalized_value
= giá trị sau khi KIE chuẩn hóa.
```

Backend phải có khả năng lưu kết quả dự đoán trước khi người dùng chỉnh sửa.

---

## 9. Receipt Status

Receipt sử dụng tối thiểu các trạng thái:

```text
UPLOADED
PROCESSING
NEEDS_REVIEW
VERIFIED
FAILED
```

Luồng cơ bản:

```text
UPLOADED
    |
    | start processing
    v
PROCESSING
    |
    +--------------------+
    |                    |
    | success            | error
    v                    v
NEEDS_REVIEW           FAILED
    |                    |
    | verify             | retry
    v                    |
VERIFIED                |
                         |
                         +----> PROCESSING
```

### Ý nghĩa

#### UPLOADED

Ảnh hóa đơn đã được Backend nhận và lưu thành công.

#### PROCESSING

Hóa đơn đang được OCR/KIE xử lý.

#### NEEDS_REVIEW

OCR/KIE đã trả kết quả nhưng dữ liệu cần được người dùng kiểm tra hoặc chỉnh sửa.

#### VERIFIED

Người dùng đã kiểm tra và xác nhận dữ liệu hóa đơn.

#### FAILED

Quá trình xử lý hóa đơn gặp lỗi.

---

## 10. Backend Responsibilities

Backend chịu trách nhiệm:

- Nhận ảnh hóa đơn từ Frontend.
- Validate request.
- Tạo receipt.
- Quản lý `receipt_id`.
- Lưu ảnh hóa đơn vào Storage.
- Quản lý trạng thái của receipt.
- Điều phối quá trình OCR.
- Điều phối quá trình KIE.
- Nhận và lưu kết quả OCR/KIE.
- Lưu giá trị dự đoán trước khi người dùng chỉnh sửa.
- Trả dữ liệu có cấu trúc cho Frontend.
- Xử lý lỗi giữa các module.

Frontend không truy cập trực tiếp Database, OCR hoặc KIE.

---

## 11. Integration Conventions

### API Version

```text
/api/v1
```

### JSON Field Naming

Sử dụng:

```text
snake_case
```

Ví dụ:

```text
receipt_id
store_name
normalized_value
source_block_id
```

### Confidence

Sử dụng số thực:

```text
0.0 -> 1.0
```

### Bounding Box

Format đề xuất:

```text
[x1, y1, x2, y2]
```

Format này cần được OCR/KIE xác nhận.

### Date

Format đề xuất:

```text
YYYY-MM-DD
```

Ví dụ:

```text
2026-08-10
```

### Datetime

Sử dụng ISO 8601.

### Encoding

```text
UTF-8
```

---

## 12. Contract Version

Phiên bản hiện tại:

```text
Integration Schema v1
```

Mọi thay đổi ảnh hưởng tới:

- tên field;
- kiểu dữ liệu;
- OCR output;
- KIE input;
- KIE output;
- bounding box;
- confidence;
- receipt status;

phải được trao đổi với các module liên quan trước khi merge.

---

## 13. Items cần xác nhận trước khi freeze v1

Các thành viên Backend, OCR và KIE cần xác nhận:

- [ ] 5 field key: `store_name`, `date`, `total`, `invoice_id`, `address`.
- [ ] OCR block có `block_id`.
- [ ] OCR block có `order`.
- [ ] Bounding box sử dụng `[x1, y1, x2, y2]`.
- [ ] Confidence sử dụng khoảng `0.0 - 1.0`.
- [ ] KIE dùng `source_block_id` để tham chiếu OCR block.
- [ ] Format chuẩn hóa của `date`.
- [ ] Format chuẩn hóa của `total`.
- [ ] Cách Backend truyền ảnh/image reference cho OCR.