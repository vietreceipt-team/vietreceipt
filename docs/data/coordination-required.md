> Feedback lead 24/10/2026: [bảng nghiệm thu từng mục, artifact và việc cần phối hợp](lead-feedback-acceptance.md). Đã giữ riêng 38 mẫu public chưa map; 80 mẫu vẫn cần reviewer độc lập. Không pull/fetch trong lần xử lý này.

# Việc cần phối hợp để nghiệm thu #47 và bàn giao TV4

Cập nhật 24/10/2026: TV4 đã publish PR #69. Xem [yêu cầu mới, kết quả xử lý và hướng dẫn review](tv4-review-followup.md).

Đây là danh sách phụ thuộc cụ thể, không dùng để trì hoãn phần TV2 tự làm.
Các script, public audit và source/evidence package được chuẩn bị trên nhánh
codex/47-tv2-dataset-completion. Không tự ghi VERIFIED hoặc ký thay người review.

| Việc | Ai cần tham gia | TV2 đã chuẩn bị | Cần xác nhận/bàn giao cụ thể |
| --- | --- | --- | --- |
| Contract evaluator A/B mới | TV4 (#49) | Gói train/validation, source regions, actual evidence, candidate gold, failures và integrity checker | Đã publish tại PR #69 head 1e7b407; TV2 đã chuẩn bị manifest theo schema mới và replay 80/80 paired pass contract. Còn đồng ký experiment và QA thực tế trước scored A/B. |
| Protocol/mẫu số/status/scope | TV1 + TV2 + TV4 + TV5 | Source inventory đầy đủ, UNKNOWN/PRESENT giữ nguyên, source-level row regions và báo lỗi từng record/cell | Co-sign protocol: UNKNOWN bị loại khỏi value metrics; NOT_PRESENT chỉ khi nguồn thực sự vắng; failure của eligible input vẫn nằm mẫu số; complete invoice gồm 13 headers + line items, tax_breakdown chưa gồm. |
| QA liên kết source với OCR | TV2 + người review độc lập; TV4 kiểm tra cách dùng | index.html của toàn bộ 80 record, source PDF/PNG, source gold, vùng ô/dòng, observed OCR và ID block thật, review-template.json | Kiểm tra nguồn và từng ID; điền reviewed_by/reviewed_at/approved sau review thật. Không dùng prediction làm gold. Ô OCR mất block giữ nguyên source gold, không invent ID. |
| Kiểm tra reader mới của TV3 | TV3 (#48, PR #65) | Output thật của reader main đang có, runtime/model/config/source hash, 3 route, log đầy đủ | TV3 xác nhận contract/geometry và có cần chạy lại bằng thay đổi reader chưa merge trong #65 hay không. Không chặn việc chuẩn bị data phía TV2. |
| Chọn bản SROIE cho benchmark | Lead/TV1 | Đã tải/audit 626 train samples từ jsdnrs curated, giữ native words/boxes/entities, snapshot và NOTICE | Chọn dùng bản curated có sửa đổi được ghi rõ hay yêu cầu archive ban tổ chức. Không gọi bản curated là original archive; không trộn số liệu hai version. |
| Independent mock test | Một người thiết kế khác + người kiểm tra nhãn thứ hai, TV1 chốt | Intake checklist, schema, provenance/split/QA/freeze tools | Tạo layout không tái dùng generator chính, annotate và review độc lập, bàn giao hashes. Không thể tự đổi tên synthetic thành independent. |
| Freeze test/config và đánh giá cuối | TV1/TV2 + TV3/TV4/TV5 | Development manifests tách train/validation, final test không nằm trong gói; freeze/evaluation tools | Chốt cấu hình trước final run, duyệt bộ test chưa dùng để tuning, ký QA, chạy final benchmark và review kết quả. |
| Source-level end-to-end denominator | TV5 + TV4, TV1 duyệt | Source regions/rows độc lập OCR và inventory giữ toàn bộ source/reader failures | TV5 chạy từ file gốc, giữ failures; TV4/TV1 thống nhất source-spatial row matching. Shared-evidence grouping không tự trở thành kết quả end-to-end. |
| Raw normalization oracle nếu chạy E3 | TV2 reviewer + TV4 | selected_value_text từ render source, không lấy text prediction; evidence gốc giữ nguyên | Chốt selected-value-text-v1, QA raw strings; oracle chỉ thay text trên ID/geometry gốc đã duyệt. Gói hiện tại không bàn giao oracle giả. |

## Luồng review thực tế

1. Giải nén gói TV4, mở index.html. Mọi record được liệt kê, kể cả reader/alignment lỗi.
2. Với từng record, kiểm tra source-preview/source gốc, source-gold, source regions,
   evidence và các block ứng viên. Template bắt đầu approved=false.
3. Reviewer sửa links nếu cần, chỉ dùng block có thật. Nếu không có block phù hợp,
   giữ unresolved; record đó không trở thành aligned verified gold.
4. Khi có review thật, dùng link_evidence trên review-source-gold.json (bản sao
   chỉ đổi identity cho từng file) cùng evidence và review JSON. Gold gốc được giữ.
5. TV4 chạy gate bằng contract mới đã publish. Exit 2/failures là chưa đạt;
   không đổi nhãn hay qa_status để ép chạy. TV1 duyệt claim/mẫu số trước final run.

Không có nội dung nào trong tài liệu này là chữ ký QA hoặc sự phê duyệt của lead.
