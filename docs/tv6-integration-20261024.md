# TV6 — kiểm tra integration và chuẩn bị demo ngày 24/10/2026

## Phạm vi theo review

Ưu tiên ổn định Frontend hiện có: đồng bộ các dependency đã merge, chạy lại luồng thật và chuẩn bị kịch bản/bằng chứng bảo vệ. Không thêm tính năng giao diện hoặc đổi thuật toán. Nội dung review người dùng cung cấp được dùng làm yêu cầu; bản protocol/worksheet vẫn chờ TV1 chốt thiết kế nghiên cứu.

## Mã nền được kiểm tra

| Thành phần | Trạng thái khi bắt đầu | Phạm vi tiếp nhận |
|---|---|---|
| `main` | `07c7cd00b0a12a555ec98f1ba45c7d1f1584e5eb` | Đã merge vào nhánh PR #68, không đẩy trực tiếp main |
| Backend #70 | Đã merge 24/10 | Worker ghi SHA-256/MIME/số byte của nguồn; source-evaluation tooling |
| KIE #69 | Đã merge 24/10 | Grouping/evaluator mới; production grouping mặc định vẫn baseline |
| Reader #65 | Còn mở | Không lấy code chưa merge vào lượt integration này |
| KIE follow-up #71 | Còn mở | Theo dõi cho lần kiểm tra sau merge |

Không mở final/test hoặc dùng pending gold để chấm accuracy. Backend source-evaluation mới là phạm vi TV5/TV4; TV6 kiểm tra hợp đồng và luồng UI, không tự duyệt gate nghiên cứu.

## Kiểm tra cần đạt trên mã nền mới

- Typecheck, lint, build, 58 unit tests và 30 browser tests của Frontend hiện có.
- 4 browser E2E với provider canonical: JPG, PDF chữ, PDF scan và PDF challenge hai trang.
- Worker input identity khớp SHA-256, MIME và số byte của file upload — kiểm tra trực tiếp metadata mới từ #70.
- Review header/dòng/thuế, nguồn nhiều trang, 409 thật và reload giữ draft, verify, export và immutable machine snapshot.
- Challenge giữ machine PRESENT sai trước sửa, ảnh inspector sau sửa và video kết quả cuối. UNREADABLE/null phải giữ nguyên trong **cả JSON, CSV ZIP và XLSX**.
- Workflow được nối trigger push main khi Backend/Reader/KIE/contracts/dependency thay đổi, có manual dispatch. Khi #68 chưa merge, cần cập nhật nhánh và chạy PR workflow như lượt này; chưa tuyên bố đã có lịch chạy trên main.

Lượt CI mới sẽ ghi kết quả/commit/artifact sau khi chạy; không dùng 4/4 ngày 23/10 để suy ra integration mới đã đạt.

## Demo và user study

[Kịch bản bảo vệ](tv6-defense-demo.md) chọn bốn file cụ thể, có thứ tự trình diễn, lời dẫn, thao tác sửa/verify/export, 409 tùy chọn, checklist giữ evidence và video dự phòng. [Hướng dẫn chạy lại](tv6-review-demo.md) tiếp tục áp dụng.

TV1 phụ trách chốt thiết kế nghiên cứu. TV6 giữ protocol/worksheet ở trạng thái chuẩn bị; nếu tổ chức pilot sẽ phối hợp đo thời gian, số lần sửa và độ đúng sau review, có consent. Chưa có người tham gia hoặc kết quả user study.
