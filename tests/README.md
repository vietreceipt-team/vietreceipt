# Tester VietReceipt

Thư mục này chứa các tài liệu và mã kiểm thử cho hệ thống VietReceipt.

## Phạm vi chính

- Kiểm thử đơn vị
- Kiểm thử tích hợp
- Kiểm thử API
- Kiểm thử luồng xử lý hóa đơn
- Kiểm thử giao diện khi cần
- Kiểm thử lỗi và tình huống bất thường
- Kiểm tra tính ổn định trước khi triển khai

## Thành viên phụ trách chính

Đặng Quang Trung — DevOps, QA và phân tích hệ thống

## Các luồng quan trọng cần kiểm thử

- Tải ảnh hóa đơn lên hệ thống
- Xử lý OCR
- Trích xuất thông tin
- Chỉnh sửa thông tin
- Xác nhận hóa đơn
- Lưu lịch sử chỉnh sửa
- Tìm kiếm hóa đơn
- Xuất dữ liệu
- Xử lý lỗi khi OCR thất bại
- Xử lý file không hợp lệ

## Nguyên tắc

- Mỗi lỗi đã sửa nên có kiểm thử tương ứng nếu phù hợp.
- Các API quan trọng phải có kiểm thử.
- Không chỉ kiểm thử trường hợp chạy đúng.
- Phải có kiểm thử cho trường hợp lỗi.
- Kết quả kiểm thử phải có bằng chứng khi dùng để nghiệm thu task.
- Mọi thay đổi phải gắn với GitHub Issue tương ứng.
