# TV6 + TV1 — pilot thao tác kiểm tra hóa đơn (dự thảo)

## Trạng thái và đồng ý

Chưa tuyển người, chưa thu số liệu và chưa có kết luận. TV1 cần duyệt protocol và đáp án synthetic trước khi bắt đầu. Người tham gia có thể từ chối/rút lui bất kỳ lúc nào. Chỉ dùng tài liệu giả; không thu ảnh, OCR text, giá trị trường, tên, email hoặc mã hóa đơn cá nhân.

Nút “Thử nghiệm thao tác tự nguyện” trong review V2 yêu cầu xác nhận hóa đơn giả và đồng ý; bộ đếm chỉ chạy từ thời điểm bấm Bắt đầu đo. Dữ liệu ở bộ nhớ, không gửi server/localStorage/cookie. Rút đồng ý xóa bộ đếm hiện tại; tệp đã chủ động tải về do người giữ tệp xóa. Không bật đo hồi tố hoặc đưa browser tự động vào số liệu người tham gia.

## Thiết kế đề xuất

Hai điều kiện: MANUAL nhập vào worksheet trống từ hóa đơn mock; ASSISTED dùng review V2. Chia đều thứ tự MANUAL→ASSISTED và ASSISTED→MANUAL, đổi bộ hóa đơn tương đương giữa hai lượt để giảm học thuộc. V1 C1/C2 là legacy năm trường, không dùng làm baseline V2 13 header và dòng hàng.

Cùng TV1 chốt số người, số mẫu và cách đối chiếu trước đo. Bài tập có một giá trị PRESENT sai, một UNREADABLE và dòng ở trang 2. Người dùng tìm lỗi, sửa phần đọc được, giữ trạng thái không đọc được, xác nhận và xuất. Không khuyến khích đoán giá trị bị che.

## Chỉ số và worksheet

- `active_review_ms`: thao tác assisted sau consent, loại tab ẩn và chờ lưu/cập nhật/xác nhận; không bao gồm upload/processing. Dùng đồng hồ theo cùng quy ước cho MANUAL; ghi mọi gián đoạn ngoài ứng dụng.
- `corrections`, `confirmations`: chỉ đếm PATCH thành công; lưu cùng giá trị/trạng thái là confirmation. Một lần sửa ô dòng tính một correction, không tính theo số phím. Không đếm 409/lỗi lưu.
- `unresolved_count`, `final_correct`, `final_eligible`: TV1 chấm bản đã xuất với đáp án mock và quy tắc trạng thái; không suy từ VERIFIED. Ghi rõ header/line/tax và mẫu số, không gộp machine accuracy với final correctness.
- Phản hồi tùy chọn theo thang 1–5: hiểu trạng thái, tìm nguồn, sửa dòng. Chỉ ghi điểm; tránh văn bản tự do chứa nội dung cá nhân.

[Worksheet trống](verification/tv6-20261023/pilot-worksheet.csv) chỉ chứa số thứ tự lượt vô danh do TV1 quản lý tại buổi thử, thứ tự điều kiện và số đếm. Không đặt receipt ID/participant ID vào JSON telemetry. TV1 giữ bảng liên kết đồng ý riêng nếu cần theo protocol được duyệt; không commit bảng này.

Chỉ công bố aggregate sau khi đo, gồm n người/n hóa đơn, thứ tự điều kiện, thời gian, số sửa, độ đúng cuối và giới hạn mẫu nhỏ. Không tuyên bố giảm X% thời gian/nhập liệu trước khi có kết quả. Machine snapshot của demo kỹ thuật tách khỏi bảng người dùng.
