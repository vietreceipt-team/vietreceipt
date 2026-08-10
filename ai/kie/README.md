# KIE VietReceipt

Thư mục này chứa phần trích xuất thông tin chính từ kết quả OCR của hệ thống VietReceipt.

## Phạm vi chính

- Nhận dữ liệu OCR đã chuẩn hóa
- Phát hiện các trường thông tin quan trọng
- Chuẩn hóa giá trị sau khi trích xuất
- Gán độ tin cậy cho từng trường
- Liên kết trường dữ liệu với vùng OCR tương ứng
- Hỗ trợ lưu giá trị dự đoán và giá trị người dùng chỉnh sửa

## Các trường thông tin chính

Phiên bản đầu tiên tập trung vào:

- Tên cửa hàng
- Ngày
- Tổng tiền
- Mã hóa đơn
- Địa chỉ

## Đầu vào

- Văn bản OCR
- Bounding box
- Độ tin cậy OCR
- Thứ tự và vị trí các vùng văn bản

## Đầu ra

Mỗi trường cần có tối thiểu:

- Loại trường
- Giá trị gốc
- Giá trị đã chuẩn hóa
- Độ tin cậy
- Tham chiếu tới vùng OCR liên quan
- Thành viên phụ trách chính

Bình Minh — KIE và kỹ thuật dữ liệu

Nguyên tắc
Không phụ thuộc cứng vào một định dạng OCR riêng nếu có thể tránh.
Các quy tắc trích xuất phải có thể kiểm thử.
Phải lưu được giá trị dự đoán trước khi người dùng chỉnh sửa.
Mọi thay đổi phải gắn với GitHub Issue tương ứng.

Ví dụ:

```json
{
  "field": "total",
  "raw_value": "325.000",
  "normalized_value": "325000",
  "confidence": 0.91,
  "source_block_id": "block_12"
}
