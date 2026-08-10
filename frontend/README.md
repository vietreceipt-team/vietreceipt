# Frontend VietReceipt

Thư mục này chứa mã nguồn giao diện người dùng của hệ thống VietReceipt.

## Phạm vi chính

- Đăng nhập và đăng ký
- Tải ảnh hóa đơn lên hệ thống
- Danh sách hóa đơn
- Trang chi tiết hóa đơn
- Hiển thị ảnh và vùng OCR
- Hiển thị các trường thông tin đã trích xuất
- Cho phép người dùng chỉnh sửa dữ liệu
- Xác nhận hóa đơn sau khi kiểm tra
- Hiển thị trạng thái xử lý
- Dashboard và các màn hình liên quan

## Thành viên phụ trách chính

Phạm Duy Đức Tâm— Frontend và giao diện Human-in-the-Loop

## Nguyên tắc

- Không gọi trực tiếp OCR từ giao diện.
- Frontend giao tiếp với hệ thống thông qua API của backend.
- Không lưu thông tin bí mật trong mã nguồn frontend.
- Mọi thay đổi phải gắn với GitHub Issue tương ứng.
