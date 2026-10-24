# Bàn giao bộ mock độc lập cho final evaluation

**Trạng thái: chưa có dữ liệu, chờ lead phân công người thiết kế khác.** Đây là
intake để nhận dữ liệu, không phải bộ test hoàn chỉnh hay bằng chứng independence.
TV2 có thể hỗ trợ format/QA; không tự sinh thêm bằng generator hiện tại rồi gọi là
independent. Lead/TV1 chốt số lượng, nhóm layout và scope trước khi tạo.

| Vai trò | Cần ghi nhận thật |
| --- | --- |
| Người thiết kế khác tác giả generator chính | Tên; ngày; công cụ/template nguồn; xác nhận không tái sử dụng layout/code/render spec hoặc base document của generator chính |
| Người gán nhãn từ nguồn | Tên; ngày; phiên bản schema; nhãn đọc trực tiếp trên source, không lấy prediction |
| Reviewer độc lập khác người gán nhãn | Tên; ngày; hash file/nhãn/vùng đã xem; kết quả/sửa lỗi/unresolved |
| TV1/lead | Duyệt provenance, scope, independence, protocol và freeze trước final run |
| TV2 | Kiểm schema/arithmetic/visible-labels/hash, duplicate/template/base leakage; tạo manifest sau khi đủ review |
| TV3/TV4/TV5 | Reader/evaluator/config chính thức, source-level denominator và xử lý failure |

Mỗi mẫu cần source PDF hoặc PNG/scan, source gold 13 headers + 5 ô mỗi dòng,
source cell/row regions độc lập OCR; sample/template/base/parent IDs, license,
nguồn/version, tác giả thiết kế/nhãn/reviewer, ngày và SHA256. UNKNOWN/UNREADABLE/
AMBIGUOUS phản ánh nguồn, không ép đủ bằng nhãn giả. Có hàng thiếu unit thì ghi
trạng thái đúng theo protocol; không thêm text không hiện trên ảnh.

Trước khi nhận: đối chiếu source/template/base và hash với **toàn bộ** train/dev,
không chỉ với 80 inputs trong gói TV4. Tương tự nội dung hay bố cục cần human review,
hash khác không chứng minh không leakage. Lưu cả record bị loại và lý do.

Final test phải giữ riêng khỏi gallery dev/tuning. TV1 chốt người giữ dữ liệu và
thời điểm mở khóa. Chỉ freeze sau QA, config/protocol sign-off; lưu manifest/hash
và không sửa nhãn bằng kết quả model sau khi xem accuracy. Bộ hiện chưa tồn tại,
do đó không có số lượng final, final hash hoặc ngày freeze để công bố.
