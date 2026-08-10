# Kiến trúc hệ thống VietReceipt

Tài liệu này mô tả kiến trúc tổng thể của hệ thống VietReceipt.

## 1. Luồng xử lý chính

Ảnh hóa đơn
→ Tiền xử lý ảnh
→ OCR
→ Trích xuất thông tin
→ Người dùng kiểm tra và chỉnh sửa
→ Lưu dữ liệu có cấu trúc
→ Tìm kiếm, thống kê và xuất dữ liệu

## 2. Các thành phần chính

- Frontend: giao diện người dùng và màn hình kiểm tra hóa đơn
- Backend: API, xác thực, xử lý nghiệp vụ
- OCR: nhận diện văn bản và bounding box
- KIE: trích xuất các trường thông tin chính
- Cơ sở dữ liệu: lưu hóa đơn, trường dữ liệu và lịch sử chỉnh sửa
- Lưu trữ tệp: lưu ảnh hóa đơn
- DevOps/QA: triển khai, kiểm thử và giám sát

## 3. Các trường thông tin chính

Phiên bản đầu tiên tập trung vào:

- Tên cửa hàng
- Ngày
- Tổng tiền
- Mã hóa đơn
- Địa chỉ

## 4. Trạng thái xử lý hóa đơn

- UPLOADED
- PROCESSING
- NEEDS_REVIEW
- VERIFIED
- FAILED

## 5. Nguyên tắc

- OCR không được giả định là luôn chính xác.
- Người dùng phải có khả năng chỉnh sửa kết quả.
- Hệ thống phải lưu lại kết quả dự đoán và giá trị đã chỉnh sửa.
- Các module phải giao tiếp qua giao diện dữ liệu rõ ràng.
- Không lưu thông tin bí mật hoặc dữ liệu nhạy cảm trực tiếp trong kho mã nguồn.
