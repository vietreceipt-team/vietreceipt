> Feedback lead 24/10/2026: [bảng nghiệm thu từng mục, artifact và việc cần phối hợp](lead-feedback-acceptance.md). Đã giữ riêng 38 mẫu public chưa map; 80 mẫu vẫn cần reviewer độc lập. Không pull/fetch trong lần xử lý này.

> Cập nhật 24/10/2026: [TV4 đã publish contract; TV2 đã chuẩn bị manifest và phiếu review mới](tv4-review-followup.md). Các mô tả chưa publish bên dưới là lịch sử của lần bàn giao 23/10. QA vẫn PENDING_REVIEW.

# TV2 follow-up: phần tự xử lý và phụ thuộc nghiệm thu

Ngày: 23/10/2026. Tiếp tục #47 / PR #66 theo yêu cầu TV4.

## Phần đã thực hiện

- Gói Git tại data/handoffs/tv4-dev-v1.zip: 80 input từ 20 hóa đơn gốc,
  tách train/validation theo family, không có test/final mock.
- Chạy reader thật 80/80, lỗi reader 0; giữ mọi output và log.
- Có source gold độc lập OCR, 13 header + 5 ô/dòng, vùng nguồn ô/dòng,
  source/evidence hashes, receipt/run IDs và phiên bản thư viện/model/config.
- 80 record có ID block spatial ứng viên thật; mọi ô OCR sai chữ được ghi riêng,
  không đổi gold hoặc giả ID. Đây là đề xuất mapping, chưa phải 80 gold VERIFIED.
- Manifest train 60 files / 15 base; validation 20 files / 5 base. Membership và
  artifact hashes được chốt cho gói dev; final test không bị đưa vào gallery.
- Integrity gate PASS: hash, contract evidence, giữ nguyên source values/status,
  ID block có thật, vùng nguồn, count, không trùng base/template/content giữa split.
- Gallery đầy đủ và review-template.json approved=false cho từng record.
- Public audit mở rộng và mapping version public-mapping-0.2:

| Dataset | Native train đã audit | Map được | Chưa map, giữ report |
| --- | ---: | ---: | ---: |
| Vietnamese Bill Extraction | 982 | 969 | 13 số tiền/format cần xem nguồn và chốt quy tắc |
| CORD, shard train đầu | 200 | 176 | 24 format/semantics số cần review |
| SROIE curated bởi jsdnrs | 626 | 625 | 1 total âm -1.73, cần chốt scope; không làm tròn/đổi dấu |

Ảnh/public native labels nằm ngoài Git. Registry giữ snapshot, attribution,
NOTICE, số mẫu thực, mask và QA reports. SROIE giữ words/boxes/entities gốc của
bản curated. Không gọi bản này là original organizer archive hoặc đánh giá final.
Mọi sample được map đã qua automated schema/hash/image/mask QA; không tự nhận
đã được người độc lập review. Không lấy label thiếu làm extraction failure.

## Phần cần phối hợp, ghi rõ người và hành động

Xem coordination-required.md. Các điểm thực sự chưa thể tự nghiệm thu:

1. TV4 push contract evaluator/grouping mới như ảnh, gồm --output, test module
   và experiment schema. Git remote hiện đọc được chưa có các phần này.
2. TV1/TV2/TV4/TV5 xác nhận protocol, UNKNOWN/NOT_PRESENT, mẫu số failure,
   shared-evidence vs source-level end-to-end, scope 13 header + line items
   chưa gồm tax_breakdown. Không tự sửa scope hoặc declaration để vượt gate.
3. Reviewer kiểm tra nguồn và mapping trên gallery, điền tên/thời điểm phê duyệt
   thật. TV3/TV4 kiểm tra geometry/reader version. Tất cả record vẫn PENDING_REVIEW.
4. Lead chốt dùng SROIE curated hay yêu cầu archive gốc; người review adjudicate
   các native label bị từ chối thay vì sửa tự động theo prediction.
5. Người khác thiết kế independent mock + reviewer độc lập; sau đó TV1 chốt
   cấu hình và freeze test chưa dùng để tuning, nhóm chạy final evaluation.
6. Oracle selected-value-text-v1 chỉ bàn giao sau QA raw values và protocol;
   hiện không có oracle giả. Source selected_value_text đã có để reviewer kiểm tra.

## Bằng chứng và lệnh chạy

- docs/data/tv4-verification/: summary, integrity, runtime/models, failures, tests.
- docs/data/tv4-contract-compatibility.json: yêu cầu evaluator so với code đang có.
- docs/data/tv4-handoff.md: tái tạo, review và dùng gói dữ liệu.
- 108 test PASS, Ruff PASS; không công bố accuracy hoặc final-result table khi
  chưa có protocol/QA đủ điều kiện. #47 vẫn chưa được đóng.
