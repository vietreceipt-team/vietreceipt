# TV6 — tiến độ kiểm tra hóa đơn và bàn giao ngày 23/10/2026

## Đầu vào đã kiểm tra

| Nguồn | Phần tiếp nhận | Giới hạn |
|---|---|---|
| [Issue #51](https://github.com/vietreceipt-team/vietreceipt/issues/51) | Review đúng trạng thái, click nguồn, sửa/409/verify/export, thử nghiệm tự nguyện | Nghiệm thu cần bằng chứng trình duyệt trên provider thật |
| [Issue #59](https://github.com/vietreceipt-team/vietreceipt/issues/59) | Ba nguồn đầu vào, tách machine/reviewed, tái lập bằng commit và cấu hình | Không suy ra accuracy hoặc tiết kiệm thời gian từ smoke test |
| PR #54 đã merge | Frontend V2 và contract tests | Bộ test cũ dùng HTTP provider kiểm thử |
| PR #62/#67 đã merge | Backend thật, immutable machine-results, Reader/KIE callable, xuất dữ liệu | Bằng chứng TV5 là HTTP; không thay bằng chứng tương tác UI của TV6 |
| TV1 PR #64 | Protocol dự thảo và điều kiện pilot | Chưa có người tham gia, co-sign hay kết quả nghiên cứu |
| TV2 #66 / TV3 #65 | Dữ liệu development và chẩn đoán Reader | Không mở final/test, không merge các nhánh của thành viên khác |

Mã nền: `main` tại `0f974abd1887f9f0bf9014eabb66cc3e48684cbb`.

## Phần TV6 bổ sung

- Viewer chờ evidence sẵn sàng trước khi chọn vùng; dùng `page_index` thực, giữ trang thiếu. Chọn trường/dòng tự chuyển trang và cuộn **trong viewer** tới vùng nguồn; zoom/xoay vẫn giữ vùng thấy được. Click vùng nguồn chọn lại trường liên quan.
- Mỗi header/ô dòng/ô thuế hiển thị trạng thái PRESENT/NOT_PRESENT/UNKNOWN/AMBIGUOUS/UNREADABLE bằng tiếng Việt cùng nhãn “Dự đoán máy” hoặc “Đã đối chiếu”. Có giá trị không đồng nghĩa đã được người dùng kiểm tra. Inspector giữ máy đọc và người sửa riêng.
- Giữ null và trạng thái thiếu/khó đọc; chuyển sang PRESENT mà để trống bị chặn. Mutation có kết quả không chắc chắn (mất mạng/5xx/2xx sai contract) khóa ghi tiếp và yêu cầu tải bản mới; không replay ngầm.
- Thử nghiệm V2 chỉ bắt đầu sau đồng ý rõ ràng trên hóa đơn giả. Chỉ giữ số lần sửa/xác nhận theo loại trường, thời gian hoạt động và outcome trong bộ nhớ trang. Loại thời gian tab ẩn và chờ correction/reload/verify; không chứa nội dung hóa đơn, receipt/row/participant ID. Rút đồng ý xóa bộ đếm; tải lại trang cũng mất số liệu.
- Thêm fixture và bộ Playwright riêng dùng API/PostgreSQL/Redis/Celery/TV3/TV4 thật, không chặn HTTP: 3 định dạng và PDF challenge hai trang. Lưu nguồn/hash, machine trước/sau, bản review, lịch sử, ảnh/video, JSON/CSV ZIP/XLSX và provenance.

## Kiểm chứng

| Phép kiểm | Kết quả tại thời điểm bàn giao ban đầu |
|---|---|
| `npm ci` | Đạt, audit 0 vulnerabilities |
| `npm run typecheck` | Đạt |
| `npm test` | 58/58 đạt |
| `npm run lint`, `npm run build` | Đạt |
| `npm run test:e2e` | 30/30 đạt; HTTP provider kiểm thử |
| PDF trang 2, dòng 60 ở cuối trang, zoom/xoay | Đạt trong browser provider test; ảnh `v2-long-table-source.png` |
| Bốn trạng thái null + PRESENT sai OCR | Đạt; không tự PATCH/xác nhận, không ghi đè machine |
| Consent/rút đồng ý, response mất và evidence tải chậm | Đạt bằng unit/browser tests |
| Browser provider thật | Theo dõi workflow **TV6 real-provider browser review** của PR; chưa gán PASS trước khi chạy |

Máy phát triển Windows dùng Node 24.19.0/Python 3.13.7, không có Docker/WSL hoặc Python 3.12. Lượt nghiệm thu thật được chạy trên GitHub Ubuntu x86_64/Python 3.12 với provider canonical và dịch vụ riêng. Kết quả, commit và link artifact được bổ sung sau khi workflow kết thúc; lỗi cũng giữ evidence. Không coi test provider là bằng chứng AI thật.

## Còn mở trên issue #51

1. TV1 cùng TV6 duyệt protocol, tuyển người tự nguyện và chạy manual/assisted có counterbalance trên mock. Worksheet chưa có dữ liệu người tham gia. Cần chấm final correctness riêng bằng đáp án đã duyệt; không dùng trạng thái VERIFIED làm accuracy.
2. TV1/leader nghiệm thu UI và bộ ảnh/video/provider thật; review PR trước merge. Không tự merge hoặc đóng issue chỉ vì CI xanh.
3. Kết quả demo synthetic chỉ chứng minh luồng thao tác trên số mẫu đã ghi, không chứng minh unseen-template accuracy, hiệu suất hay phần trăm tiết kiệm thời gian.

Lệnh chạy và artifact: [hướng dẫn TV6](tv6-review-demo.md). Thiết kế pilot: [protocol và worksheet](tv6-pilot-protocol.md).
