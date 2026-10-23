# Bàn giao local TV4 — #49 / #59

Cập nhật 23/10/2026 sau PR #66 (TV2) và #65 (TV3). Chi tiết và nguồn tại
[intake + gallery](kie49-tv2-intake.md), công thức tại
[protocol](kie-v2-grouping-experiment.md). Patch sẵn sàng review local;
chưa push/mở PR theo yêu cầu ban đầu. Không thêm `Closes #49`.

## Nội dung để bạn gửi TV1/TV2/TV3/TV5 (chưa gửi)

> TV4 đã tiếp nhận ZIP PR #66 head `8a6033`, kiểm hash/identity/split, replay cả hai
> cấu hình trên 80 evidence thật: 80/80 paired pass contract. Đã kiểm gói TV3 PR #65
> head `036b775`: 54/54 paired pass cả KIE và backend V2 contracts. Hai dataset được
> giữ riêng, không trộn nhãn hoặc cộng thành benchmark. Không chạy OCR lại local.
>
> Evaluator mới `invoice-evaluation-2.2.0` có UNKNOWN masks + mẫu số strict theo
> dự thảo TV1 #64, row P/R/F1, JSON/CSV per sample và gate không đổi QA. Schema mới
> là `schemas/invoice-kie-experiment.v1.schema.json`; lấy object chính xác bằng
> `python scripts/evaluate_invoice_kie.py --print-experiment`. Baseline config
> `invoice-baseline/2.1.0`; variant `column_interval_grouping_v2_1`, config
> `invoice-column-intervals/2.2.0`. Placeholder `relation_grouping_v2_1` không hợp lệ.
>
> TV2: cần người độc lập duyệt source gold + source regions và block alignment,
> ghi reviewer/date/hash đúng thực tế, rồi tạo manifest evaluator mới theo contract.
> 80/80 candidate hiện vẫn PENDING_REVIEW; frozen membership không đồng nghĩa VERIFIED.
> Không đổi source label để khớp OCR hoặc tự cấp VERIFIED. Nếu có Reader/alignment
> failures phải giữ cohort và dùng scope đo phù hợp, không loại để làm điểm đẹp.
>
> TV1/TV2: nhờ xác nhận UNKNOWN excluded; NOT_PRESENT/UNREADABLE/AMBIGUOUS vẫn chấm
> status+null; strict cần mọi ô known; tax groups không thuộc scope. Source-spatial
> kernel đã có nhưng positive-IoU tie/geometry/failure policy vẫn cần đồng ký.
> Lead quyết định dùng #66 thay #60 và nguồn SROIE curated/gốc; TV4 chưa tự chốt.
>
> TV3: saved Reader evidence đã tương thích contract TV4 hiện tại. Cần xác nhận
> version/config/log bàn giao chính thức; train VRSYN2-00001__clean_pdf có header
> `Ten hang / dich v` và `Do'n gia`, nên variant vẫn chưa nhận bảng. TV4 giữ nguyên
> text/IDs; các lỗi còn lại có trong gallery, không gọi là đã sửa OCR.
>
> TV5: `source_metrics` nhận immutable machine result từ original file, source gold
> không có OCR IDs và vùng nguồn đã review; failure dùng None. Caller phải kiểm
> source identity/hash và coordinate transforms. Đây là kernel, chưa phải final runner.
>
> Hiện mọi accuracy benchmark/delta vẫn null. Variant có thêm output dòng nhưng
> chưa được chọn làm default. Leader cần phân công người thiết kế/ghi nhận/review
> mock độc lập; chỉ freeze và chạy final sau QA + protocol + config sign-off.

## PR draft (chưa tạo PR)

**Title:** `feat(kie): evaluate grouping safely and recover observed invoice table headers`

**Related:** #49, #59; dependency #47/#48; references #64/#65/#66. Không tự đóng issue.

Trên evidence TV2 train, header `Tên hàng / dịch vụ` không được baseline nhận diện;
ngay cả khi nhận header, `Sổ tay văn phòng` bị nhầm thành nhãn số hóa đơn và dừng bảng.
Thêm cấu hình thử nghiệm có alias chính xác, bảo vệ dòng với numeric context và
ranh giới thuế inline, cùng containment số hẹp. Provider mặc định giữ baseline.
Expected PDF text được chép từ source preview; các lỗi OCR còn nguyên trong output.

Evaluator 2.2.0 thêm paired development A/B có experiment schema, row P/R/F1,
UNKNOWN coverage/strict denominators, per-sample JSON/CSV/delta/failure reports,
kiểm canonical money và fail-closed QA gate. Source-spatial kernel riêng giữ lỗi
Reader/KIE trong mẫu số, không dùng gold OCR IDs; caller chịu trách nhiệm source QA,
identity/hash và geometry. Candidate inspector chạy unscored, không sửa gold/QA.

**Validation:** 139 tests gồm KIE V1/V2/eval/artifacts, source failure/matching,
intake integrity, baseline fingerprints 12 ca, saved PDF/PNG/scan Reader regressions
và PDFium Reader smoke; shared contracts pass, Ruff/format/diff check pass.
TV2 80/80 + TV3 54/54 evidence replay paired contract pass. Chi tiết và content hash
trong `docs/experiments/kie49/verification-20261023.json`.

**Evidence and limits:** TV2 baseline 0 input có dòng, variant 58/80, tổng 205 dòng;
đó chỉ là đếm output. 0/80 candidate reviewed, mọi benchmark accuracy và delta=null.
Một train PDF source regression xác nhận 5 dòng đúng; không suy diễn thành accuracy
trên corpus. Không chạy local PaddleOCR, không dùng final test, không chấp thuận QA.

**Integration:** config/extractor variant tăng lên 2.2.0, default signature/schema
backend không đổi. Evaluator version và mẫu số UNKNOWN thay đổi, consumer phải dùng
schema/version mới, không trộn score cũ. Complete-invoice chỉ 13 headers+line_items,
không gồm tax groups. Nhánh đã rebase lên `origin/main` tại `0f974ab`, giữ rule tiền
tệ PR #63 và artifact TV5 PR #67; CI trên remote vẫn cần đạt trước publication.

## Còn phụ thuộc người phụ trách

1. Lead review #66, quyết định thay #60 và chọn SROIE; đó không phải kết quả TV4 tự duyệt.
2. Reviewer độc lập duyệt source/alignment/regions; TV2 tạo manifest đạt gate.
3. TV1/TV2/TV5 đồng ký protocol; TV3 xác nhận Reader version; TV4 chạy scored A/B
   trên tập được duyệt, xem precision/cell/strict cùng coverage rồi mới chốt config.
4. Phân công mock độc lập và chạy final sau freeze. Chưa thể kết luận #49 đạt accuracy.
