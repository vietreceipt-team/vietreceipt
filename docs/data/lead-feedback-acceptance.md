# Tiến độ xử lý feedback lead — PR #66

Đối chiếu feedback người dùng cung cấp ngày 24/10/2026. Generator, chia layout,
hash và các kiểm tra đang pass được giữ nguyên. Không pull/fetch/merge trong lần
xử lý này; chỉ dùng code và snapshot TV4 đã có tại máy. Nếu cần pull, báo người dùng trước.

| Yêu cầu của lead | Đã thực hiện được một mình | Chưa thể nghiệm thu / cần phối hợp |
| --- | --- | --- |
| 1. Review ground truth | Gallery toàn bộ 80 mẫu; 80 phiếu gắn hash; queue từng record; kiểm tra reviewer/date/approvals/hash và không bỏ sót cohort | **0/80 được reviewer độc lập duyệt.** Lead chỉ định reviewer khác người tạo nhãn. TV2 cùng reviewer kiểm source gold, vùng ô/dòng và OCR alignment; TV3 hỗ trợ lỗi OCR/geometry. Chỉ lưu chữ ký/ngày sau review thật. |
| 2. Independent mock dataset | Mẫu intake, tiêu chí nguồn gốc/nhãn/split và quy trình bàn giao trong independent-mock-intake.md | Lead phân công người thiết kế khác, người annotate và reviewer độc lập. **Chưa có bộ mock độc lập.** Tập test do generator hiện tại sinh không đáp ứng mục này. |
| 3. Dataset handoff sau review | Gói v1 có source gold/evidence/regions/candidate aligned gold; overlay v2 có manifests đúng TV4 2.2.0; index artifact/hash, queue và hướng dẫn TV4/TV5 | Chưa có reviewed aligned gold hoặc manifest VERIFIED để bàn giao cuối. Sau review, TV2 tạo phiên bản mới, giữ originals, hash gold và review receipts; TV4/TV5 kiểm gate/contract, TV1 chốt scope/config. |
| 4. Mẫu public không map được | Đã cách ly **38/38 mẫu**: Vietnamese Bill 13, CORD 24, SROIE curated 1; giữ đủ ảnh, native labels, ID/split, nguồn/snapshot/hash và lý do; không sửa số/nhãn để ép map | Lead/TV1 chọn SROIE curated hay original. Các định dạng/số âm còn mơ hồ cần quyết định mapping/scope theo nguồn; hiện vẫn không tính là canonical gold. |

## Artifact để review

- [Gói source/evidence v1](../../data/handoffs/tv4-dev-v1.zip): 80 inputs, 20 base,
  60 train / 20 validation. Không có final test.
- [Overlay evaluator/review v2](../../data/handoffs/tv4-evaluation-intake-v2.zip):
  giải nén vào cùng gốc v1, dùng evaluator-*-manifest.json. Chưa cấp VERIFIED.
- [Danh mục artifact và hash](../../data/handoffs/lead-feedback/artifact-index.json).
- [Queue 80 phiếu review](../../data/handoffs/lead-feedback/review-queue.csv):
  assigned_to để trống vì lead chưa phân công; không điền tên hộ.
- [Báo cáo riêng 38 mẫu chưa map](../../data/registry/quarantine/README.md).
- [Quy trình TV4](tv4-review-followup.md) và [phụ thuộc cần phối hợp](coordination-required.md).

Ảnh/native labels của 38 mẫu đã được giữ tại data/processed/quarantine/ và đóng
gói tại output/datasets/public-quarantine-0.2.zip (local, ignored). Git lưu manifest
và báo cáo ID/hash/lý do, không chứa ảnh public receipts của gói quarantine.
Không coi link báo cáo Git là link tải ảnh. Gói local có thể bàn giao nguyên trạng
cho reviewer, kèm SHA256 trong artifact-index.json.

## Cách hoàn tất review thật

1. Lead chỉ định reviewer độc lập; người đó mở index.html trong gói v1 và phiếu
   reviews/<record_id>.json của overlay v2. TV2 cùng kiểm ảnh/PDF, không dựa vào
   KIE prediction để quyết định gold.
2. Duyệt từng ô source gold, vùng ô/dòng và block ID thực. Ghi lỗi/unresolved
   và nhận xét. OCR mất chữ không đổi PRESENT thành NOT_PRESENT; không tạo ID.
3. Nếu source label/region/alignment cần sửa, tạo bản dữ liệu/version mới và
   giữ nguyên bản trước. Tạo lại phiếu hash cho bản mới để reviewer duyệt; không
   tái sử dụng chữ ký trên hash cũ. Không loại mẫu lỗi khỏi cohort để làm đẹp điểm.
4. Ghi người tạo nhãn, reviewer thật khác người tạo, ngày có timezone và approval
   đúng những nội dung đã đọc. Check receipts chỉ kiểm cấu trúc/hash, chưa thay thế
   semantic validation hay phê duyệt của owner.
5. TV2 tạo reviewed aligned gold bằng quy trình link_evidence đã có (bản sao của
   source gold chỉ đổi identity và source_block_ids). TV4 kiểm validate_gold theo
   snapshot evaluator đã chốt. TV5 dùng source gold và source regions đã duyệt,
   không dùng gold có OCR IDs làm source-level truth.
6. Chỉ phát hành manifest VERIFIED khi có review thật và owner chấp thuận; ký
   protocol/experiment/config trước scored A/B. Sau đó mới bàn giao artifact version
   mới cho TV4/TV5. Final test còn chờ independent mock và freeze riêng.

## Kết luận nghiệm thu

Mục 4 hoàn tất phần giữ riêng và báo lỗi theo dữ liệu hiện có; mapping ambiguity
vẫn được công khai. Mục 1–3 đã có công cụ và gói chuẩn bị, **chưa hoàn tất phần
nghiệp vụ cần con người khác**. #47 chưa đủ điều kiện đóng. Không có accuracy,
delta cuối hoặc chữ ký reviewer được tạo tự động.

## Kiểm tra lần này

32 tests liên quan pass; Ruff pass. Đối chiếu trong ZIP: 38/38 native records giữ
nguyên byte theo export gốc và 38/38 hash ảnh khớp. Kiểm phiếu vẫn trả exit 2,
0/80 hoàn tất, đúng trạng thái chờ reviewer. Báo cáo tại
[data/handoffs/lead-feedback/verification.json](../../data/handoffs/lead-feedback/verification.json).
