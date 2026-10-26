# TV4 — tiếp nhận bàn giao TV2/TV3 ngày 23/10/2026

Đã hoàn thành phần triển khai local của #49 có thể kiểm chứng trước khi duyệt gold.
**Chưa nghiệm thu accuracy và chưa đóng #49/#47.** Baseline vẫn là provider mặc định.
Không ghi nhận reviewer/sign-off thay TV1/TV2/TV3, không sửa QA trong gói nhận.

## Artifact và phạm vi

- TV2 [PR #66](https://github.com/vietreceipt-team/vietreceipt/pull/66), head
  `8a603300071d6dbfebd23e8f22a8c9cbac90ff48`; ZIP `tv4-dev-v1.zip`, SHA256
  `6661c858c0564820a035ae0f62951647d19c74dd0c789aa4e56a072dfb4d9790`.
  Đã kiểm ZIP CRC, hash từng source/evidence/gold/regions/log/metadata, identity
  aliases, gold candidate giữ nguyên giá trị/status nguồn, split theo base/template/source hash.
  80 đầu vào = 20 hóa đơn gốc × 4 dạng; train 60/15 base/3 template,
  validation 20/5 base/1 template. Không có final test trong gói đã mở.
- Reader thực tế trong metadata TV2: PaddleOCR 3.0.3 trên ảnh/scan; PDFium 5.12.1
  cho PDF text. Đã **replay KIE trên evidence lưu sẵn**, không chạy OCR lại local.
  80 Reader success, 80 lượt paired KIE success, 0 lỗi contract/hash được phát hiện.
- Toàn bộ 80 gold alignment vẫn `PENDING_REVIEW`: máy đề xuất liên kết block.
  `frozen=true` của gói chỉ khóa membership/hash, không chứng minh QA.
  Formal evaluator giữ `WAITING_FOR_VERIFIED_V2_GOLD`, `metrics=null`,
  `evaluated=0`, mẫu số đã biết train=60, validation=20.
- TV3 [PR #65](https://github.com/vietreceipt-team/vietreceipt/pull/65), head
  `036b7754811b8c8ae45a96d4dac56550904666e2`, là dataset **v0.1 khác**:
  3 parent validation, 27 biến thể, 54 evidence ở hai route. Gói này không dùng
  chung gold/sample identity với TV2 v0.2.0. Kết quả replay riêng lưu tại
  [tv3-replay.json](experiments/kie49/tv3-replay.json); không cộng hai corpus để báo accuracy.

## Thay đổi và bằng chứng

Variant `column_interval_grouping_v2_1` giữ ID nhưng tăng config/extractor lên **2.2.0**.
Bản 2.1.0 chỉ containment số, replay lần đầu trả 0 dòng ở cả hai phương án trên 80 input.
Từ **train VRSYN2-00001** và source preview, bản 2.2.0 sửa thêm:

1. Header description nhận đúng `Tên hàng / dịch vụ` (không fuzzy-repair OCR).
2. Không dừng bảng vì sản phẩm `Sổ tay văn phòng` bị nhận thành nhãn số hóa đơn,
   khi description đi cùng ít nhất hai cột số độc lập. Không suy ra tiền bị thiếu.
3. Dừng bảng hàng tại nhãn inline `Thuế suất GTGT:` để footer không thành sản phẩm.

Test tách tác động trên cùng evidence PDF text: baseline 0 dòng; alias + tax stop
nhưng chưa bảo vệ dòng số: 3 dòng; thêm bảo vệ: 5 dòng. Expected 5 dòng chép từ
[source preview](../tests/fixtures/kie49/reader-tv2/source-preview.png), không lấy
prediction làm nhãn. Đây là regression của developer, **không thay independent QA**.
Containment vẫn có test độc lập số hẹp căn phải; normalization không đổi.

| Cohort | Số input | Baseline có dòng | Variant có dòng | Tổng dòng variant |
| --- | ---: | ---: | ---: | ---: |
| Train PDF text | 15 | 0 | 15 | 56 |
| Train PNG sạch | 15 | 0 | 13 | 52 |
| Train scan PDF | 15 | 0 | 8 | 17 |
| Train PNG mờ | 15 | 0 | 11 | 43 |
| Validation PDF text | 5 | 0 | 5 | 17 |
| Validation PNG sạch | 5 | 0 | 2 | 8 |
| Validation scan PDF | 5 | 0 | 2 | 5 |
| Validation PNG mờ | 5 | 0 | 2 | 7 |

Đây chỉ là **đếm output**, không phải true positive/recall/cell accuracy. Có thêm
205 dòng trên 58/80 input chưa chứng minh chúng đúng hoặc không dư. Row F1,
cell/complete-line, field accuracy và delta chính thức đều **null**. Không chọn
variant làm mặc định dựa trên số dòng. Chưa có oracle QA hay ablation raw-value QA.

## Gallery nguồn và giới hạn

[Gallery JSON](experiments/kie49/tv2-gallery.json) chứa refs/hash nguồn, gold candidate,
output cả hai phương án và trích evidence theo block. Full artifact local ở
`results/kie49/tv2-inspection-post-rebase/`; source đã nhận ở
`results/kie49/received/tv4-dev-v1/`.
Tất cả ví dụ dưới đây thuộc **train**, không dùng final để tìm lỗi.

| Nhóm | Bằng chứng / phân biệt nguyên nhân |
| --- | --- |
| Row grouping / header | `VRSYN2-00001__text_pdf`, `p0_b000010`: literal `Tên hàng / dịch vụ` có trên source và Reader. Regex cũ không nhận toàn nhãn. Sửa được trên ca này. |
| Candidate / role | Cùng mẫu, `p0_b000030`: `Sổ tay văn phòng` bị regex `số` nhận làm header tài liệu. Numeric context giữ đúng dòng; source có 5 dòng, regression xác nhận 5. |
| OCR substitution / unsupported header | `VRSYN2-00001__clean_pdf`, `p0_b000010`: `Ten hang / dich v`, `p0_b000013`: `Do'n gia`. Variant vẫn 0 dòng. Không tự sửa text hoặc tuyên bố KIE đã khôi phục. |
| OCR text / normalization | `VRSYN2-00001__clean_png`: `Bia ho so`, `Büt bi xanh`, `Mc may in` giữ nguyên dấu sai; tiền 7.000 → 7000 theo rule VND hiện có. Phục hồi dòng không đồng nghĩa description đúng. |
| Geometry / reading order | Numeric containment và continuation có unit regressions. Chưa có bằng chứng từ những ví dụ đã xem rằng Reader geometry là nguyên nhân của toàn bộ lỗi còn lại; cần người review overlay, không gán taxonomy máy thành nguyên nhân. |
| Gold / alignment | Các cell source khác OCR vẫn chỉ `SPATIAL_CANDIDATE_REQUIRES_REVIEW`. Source label giữ nguyên; không coi text-agreement là QA alignment. |
| Currency / VAT | Inline thuế là ranh giới bảng, không phải một line item; test bảo toàn tax grouping cũ. Chưa có tax-group gold để chấm; currency/header miss còn tồn tại trên OCR sai, không suy currency/tiền từ phép cộng. |

Không thêm các alias OCR hỏng từ scan/blur chỉ để tăng số dòng. Nguy cơ còn lại:
header OCR biến dạng, block gộp nhiều ô, partial rows, tên sản phẩm giống footer,
layout không header. Numeric guard có thể bỏ qua footer có hai cột số nên cần QA
trên nguồn và kiểm tra precision, không chỉ recall. 20 base synthetic chưa đại diện
cho hóa đơn thực; các biến thể cùng base không phải 80 mẫu độc lập.

## Contract gửi TV2/TV1/TV5

Evaluator `invoice-evaluation-2.2.0` áp dụng dự thảo TV1 PR #64: gold UNKNOWN bị
mask khỏi field/cell/presence và mẫu số strict completion; status NOT_PRESENT,
UNREADABLE, AMBIGUOUS vẫn exact-match với null. Row detection vẫn dùng mọi dòng.
Counts/coverage và mẫu số scoreable được xuất; mẫu số 0 → null. Không nhận là
protocol đã được đồng ký. VND chỉ integer JSON, USD tối đa 2 số lẻ theo main PR #63.

[Schema experiment](../schemas/invoice-kie-experiment.v1.schema.json) khóa đúng
baseline/variant/version. Dùng `python scripts/evaluate_invoice_kie.py --print-experiment`
để lấy object. TV2 đang dùng placeholder `relation_grouping_v2_1`; không đổi tên
bằng cách coi đó là alias hợp lệ. Sau khi owner duyệt cần tạo manifest evaluator
mới (giữ bản candidate), đầy đủ `configuration`, `template_regime`, reviewer,
`frozen_at`, hash gold/evidence và experiment; chỉ khi reviewer thật duyệt mới
được gắn VERIFIED. Không chỉ chép experiment rồi đổi QA flag.

`ai/kie/v2/source_evaluation.py:source_metrics(cases)` là kernel **riêng** cho TV5,
không phải runner final và không tự cấp quyền QA. Mỗi case:
`(result_or_None, source_gold, evidence_or_None, source_row_regions)`.

- Caller xác minh association original input ↔ evidence ↔ machine snapshot, source
  hash và QA vùng nguồn trước khi gọi; không dùng result sau correction của người.
- Gold không được mang bất kỳ OCR block IDs. Region có đúng một rectangle trên
  một page cho mỗi `line_id`, tọa độ top-left [0,1], không suy từ prediction.
- Prediction rectangle lấy union block IDs thực theo từng trang. Ghép một-một
  maximum cardinality khi positive IoU cùng page; cạnh ưu tiên IoU rồi prediction
  index, duyệt gold theo page/top/left/index. Không dùng giá trị/status để match.
  Không tối ưu tổng IoU toàn cục. Split/merge bị giới hạn một-một.
- Lỗi Reader/KIE dùng result=None, giữ tài liệu và mọi gold row đã biết trong mẫu số;
  strict completion sai kể cả bảng gold rỗng. UNKNOWN vẫn áp dụng mask.
- Caller phải map lại tọa độ nếu deskew/rotate/crop. Kernel không tự căn ảnh;
  một gold row trải nhiều trang chưa được hỗ trợ. Bbox union rộng có thể giao nhầm
  dòng lân cận; cần QA geometry và xem matching trước khi chốt protocol.
- Aligned evaluator vẫn fail-closed cho cả cohort khi record lỗi; kernel source
  có semantics failure riêng. Không trộn hai scope hoặc gọi module score end-to-end.

## Lệnh tái lập

Dùng Python 3.12 + `requirements-contracts.txt`; local đã dùng
`/tmp/vietreceipt-kie49-venv/bin/python`. Thư mục output phải mới.

```bash
python scripts/evaluate_invoice_kie.py --print-experiment
python scripts/inspect_invoice_handoff.py \
  --root results/kie49/received/tv4-dev-v1 \
  --output results/kie49/tv2-inspection-new \
  --source-revision 8a603300071d6dbfebd23e8f22a8c9cbac90ff48
# Exit 2: đã xử lý nhưng gold còn pending; exit 1: lỗi integrity/Reader/KIE.
python docs/experiments/kie49/replay-tv3.py \
  results/kie49/received/tv3-tv2-handoff-20261023.zip results/kie49/tv3-replay-new
python -m unittest tests.test_kie_v2_handoff tests.test_kie_v2_source_evaluation -v
```

Lấy ZIP nguyên byte bằng `git show <pinned-head>:<path-in-PR> > <local-zip>`.
TV2 path `data/handoffs/tv4-dev-v1.zip`; package metadata ở `data/handoffs/tv4-dev-v1.package.json`;
TV3 path `results/dev/tv2-reader-v0/tv3-tv2-handoff-20261023.zip`.
Không extract ZIP ngoài thư mục nhận; kiểm path traversal/CRC/hash trước khi mở.

[Bản ghi kiểm chứng](experiments/kie49/verification-20261023.json),
[intake summary](experiments/kie49/tv2-intake.json), [PR draft và tin nhắn](kie49-handoff.md).
Các snapshot cũ được giữ nguyên cùng version/hash của lần đo cũ.
