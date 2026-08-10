# Quy định đóng góp cho dự án VietReceipt

Tài liệu này quy định cách làm việc chung của toàn bộ thành viên trong dự án VietReceipt.

Mọi thành viên phải tuân thủ thống nhất các quy tắc dưới đây.


## 1. Quy định chung

- Kho mã nguồn phải luôn để ở chế độ riêng tư.
- Không được đưa mật khẩu, khóa API, mã bí mật hoặc dữ liệu nhạy cảm lên kho mã nguồn.
- Không được đưa file `.env` lên GitHub.
- Mọi công việc phát triển phải gắn với một GitHub Issue.
- Khi dự án bắt đầu làm việc nhóm, không được đẩy mã trực tiếp lên nhánh `main`.
- Mỗi thành viên phải tự chịu trách nhiệm với phần việc được giao.


## 2. Quy trình làm việc

Quy trình chuẩn của mỗi công việc:

Issue
→ Tạo nhánh riêng
→ Viết mã hoặc thực hiện công việc
→ Commit
→ Push
→ Tạo Pull Request
→ Review
→ Merge
→ Hoàn thành

## 3. Quy tắc hoàn thành công việc

Một công việc chỉ được xem là hoàn thành khi:

- Đã tạo đủ kết quả đầu ra yêu cầu.
- Có bằng chứng kiểm chứng được.
- Mã nguồn hoặc kết quả đã được đưa lên GitHub.
- Đã tạo Pull Request nếu có thay đổi mã nguồn.
- Đã được người review kiểm tra.
- Các kiểm thử liên quan đã đạt.


## 4. Quy định khi bị chặn

Nếu không thể tiếp tục công việc do phụ thuộc vào thành viên khác hoặc do lỗi kỹ thuật, thành viên phải báo ngay trong GitHub Issue.

Nội dung báo cáo phải ghi rõ:

- Bị chặn bởi công việc hoặc vấn đề nào.
- Nguyên nhân.
- Cần ai hoặc cần điều gì để xử lý.
- Thời điểm bắt đầu bị chặn.

Nếu bị chặn quá 24 giờ phải báo cho lead.

## 5. Trách nhiệm của thành viên

Mỗi thành viên có trách nhiệm:

- Hoàn thành công việc đúng thời hạn.
- Cập nhật trạng thái công việc trên GitHub.
- Báo sớm khi có vấn đề.
- Cung cấp bằng chứng cho công việc đã hoàn thành.
- Không làm ảnh hưởng đến phần việc của thành viên khác.
- Không tự ý thay đổi kiến trúc chung nếu chưa trao đổi.
- Tuân thủ quy trình Issue → Pull Request → Review.


## 6. Nguồn quản lý tiến độ chính thức

GitHub là nguồn quản lý tiến độ chính thức của dự án.

Tin nhắn trên Zalo, Messenger, Discord hoặc các nền tảng khác không thay thế cho:

- GitHub Issue
- Pull Request
- Kết quả công việc
- Bằng chứng hoàn thành
- Kết quả review

Nếu một công việc không được ghi nhận trên GitHub thì có thể được xem là chưa được tài liệu hóa.
