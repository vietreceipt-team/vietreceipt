# Backend VietReceipt

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
