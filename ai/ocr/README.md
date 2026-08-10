# OCR VietReceipt

Thư mục này chứa phần nhận dạng ký tự quang học và xử lý ảnh của hệ thống VietReceipt.

## Phạm vi chính

- Tiền xử lý ảnh hóa đơn
- Hiệu chỉnh xoay và độ nghiêng
- Cải thiện độ tương phản khi cần
- Chạy OCR
- Trả về văn bản nhận dạng
- Trả về bounding box
- Trả về độ tin cậy của OCR
- Đánh giá chất lượng OCR

## Đầu vào

- Ảnh hóa đơn

## Đầu ra chuẩn

Mỗi vùng OCR cần có tối thiểu:

- Nội dung văn bản
- Độ tin cậy
- Tọa độ bounding box


## Thành viên phụ trách chính

Bình Minh— OCR và xử lý ảnh

Nguyên tắc
Không để OCR chỉ tồn tại dưới dạng script chạy thủ công.
Phải chuẩn hóa đầu ra để backend và KIE có thể sử dụng.
Các thử nghiệm phải lưu lại cấu hình và kết quả.
Mọi thay đổi phải gắn với GitHub Issue tương ứng.
