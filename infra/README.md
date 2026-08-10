# Hạ tầng và triển khai VietReceipt

Thư mục này chứa các cấu hình liên quan đến triển khai, môi trường chạy và hạ tầng của hệ thống VietReceipt.

## Phạm vi chính

- Docker
- Docker Compose
- Cấu hình cơ sở dữ liệu
- Cấu hình lưu trữ tệp
- Biến môi trường
- Quy trình triển khai
- Nhật ký hệ thống
- Kiểm tra tình trạng dịch vụ
- Hỗ trợ môi trường phát triển và môi trường chạy thử

## Thành viên phụ trách chính

Đặng Quang Trung — DevOps, QA và phân tích hệ thống

## Nguyên tắc

- Không ghi mật khẩu hoặc khóa bí mật trực tiếp trong file cấu hình.
- Các thông tin nhạy cảm phải được truyền qua biến môi trường.
- Mọi dịch vụ phải có hướng dẫn chạy rõ ràng.
- Cấu hình triển khai phải có khả năng tái tạo trên máy khác.
- Không đưa dữ liệu hóa đơn thật vào image Docker hoặc file cấu hình.
- Mọi thay đổi phải gắn với GitHub Issue tương ứng.
