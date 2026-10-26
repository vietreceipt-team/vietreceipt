# TV3 → TV4: đo tác động Reader trên gold đã được duyệt

Cập nhật 24/10/2026. Trạng thái: **PENDING_REVIEW — chưa có KIE accuracy hoặc
route delta đủ điều kiện**. Đây là kế hoạch bàn giao development của #48/#65,
không cấp quyền chạy final test hoặc ký thay TV1/TV2/TV4/TV5.

Hợp đồng tham chiếu: evaluator `invoice-evaluation-2.2.0` từ TV4 [PR #69](https://github.com/vietreceipt-team/vietreceipt/pull/69)
(`1e7b407d1314110ce2d8411211f55f49f7eb0ffd`), đã có trên main
`07c7cd00b0a12a555ec98f1ba45c7d1f1584e5eb`; gói TV2 [PR #66](https://github.com/vietreceipt-team/vietreceipt/pull/66)
được kiểm tra tại `89281198ebaf419e511b4c99321ca3355e94fcf1`.
PR #66 còn chờ independent review. Bản source/evidence lịch sử của #65 tại
`5e5b871d` là bộ khác; không gán gold hay QA mới cho run cũ chỉ vì ID có vẻ giống.

## Hai phép đo, hai loại gold

| Phép đo | Gold / vùng nguồn | Ý nghĩa và giới hạn |
| --- | --- | --- |
| Original-file/source evaluation | Nhãn đọc từ nguồn và vùng dòng nguồn được duyệt độc lập; mọi `source_block_ids` của gold rỗng | Giữ lỗi Reader/KIE trong mẫu số; TV5 kiểm source bytes, provenance, identity, config và frame trước khi gọi source kernel |
| Aligned-evidence KIE evaluation | Bản sao nhãn nguồn với block links được người duyệt cho đúng từng evidence run | Đo KIE trên evidence đủ điều kiện; không thay cho end-to-end và không bao gồm các ca OCR mất nội dung không thể align |

Source truth giữ nguyên value/status/line IDs khi đổi Reader mode. Không đổi
`PRESENT` thành `NOT_PRESENT` khi OCR bỏ sót chữ; không chép text dự đoán vào
gold. Missing/ambiguous/shared block links ở aligned gold cần review thực tế.
Nếu không giải quyết được, giữ lý do và record trong inventory/source cohort;
khai báo riêng số aligned-eligible. Không loại ca khó khỏi source denominator.

TV4 evaluator dùng 13 headers trong `ai.kie.v2.config.HEADER_FIELDS`, và 5 ô mỗi
dòng: `description`, `unit`, `quantity`, `unit_price`, `amount`. Tax groups nằm
ngoài complete-invoice scope hiện tại. `UNKNOWN` không vào value/status score;
các status known còn lại được chấm. Strict header/table/invoice chỉ scoreable
khi các ô yêu cầu đều known. Báo cả coverage, không điền 0 thay cho metric null.

## Bàn giao định danh theo từng mode

TV3 bàn giao `handoff.json`, input manifest, SHA-256 nguồn, evidence JSON và
metadata/config/log của mỗi mode `ocr_all` / `route_aware` từ
`scripts.compare_pdf_routes`. Khóa so sánh là input record + source SHA-256;
khóa evidence là `(receipt_id, ocr_run_id, page_index, block_id)`.

Hai mode có OCR run IDs, segmentation và block IDs riêng. TV2/reviewer cần
hai bộ mapping/phiếu review riêng và hai aligned manifests. Không tái sử dụng
links của route-aware cho OCR-all, không sửa IDs của evidence để ép gold khớp.
Giữ source aliases và review hash cho mọi bản derived gold.

Mỗi aligned manifest phải có sample/receipt IDs duy nhất, hash gold/evidence
đúng byte và QA thật. Các variant #65 lịch sử dùng lại receipt UUID của base;
không nhét cả 27 variant vào một strict manifest rồi bỏ duplicate guard. Chia
cohort theo variant/condition phù hợp, hoặc dùng per-input identity đã được
owner bàn giao như #66. Ghi rõ base count và derivative file count; các biến thể
không phải những hóa đơn độc lập.

TV3 xác nhận Reader code/config/source hashes đã chạy, route/fallback, DPI,
orientation và canonical frame. Ảnh dùng frame sau EXIF transpose, trước OCR
rotation/resize; PDF dùng crop/unrotated frame. TV2 + reviewer kiểm vùng nguồn
và alignment trong cùng frame; TV4 duyệt row matching. Không tự suy ra phép xoay
hoặc tịnh tiến bằng cách tối đa hóa overlap với prediction.

## Các gate cần có trước scored run

1. TV2 + reviewer độc lập duyệt source value/status, source cell/row regions và
   hash đúng source/gold/regions. Tên người tạo nhãn, reviewer khác người tạo,
   ngày thật có timezone và artifact references phải có bằng chứng.
2. Với aligned evaluation, duyệt đúng links của **từng** mode/run, không chỉ
   kiểm schema hoặc việc ID tồn tại. PR #66 có phiếu review hash-bound và
   `scripts.data.check_tv4_reviews`; exit 0 của công cụ chỉ xác nhận cấu trúc/hash.
3. TV1/TV2/TV4/TV5 chốt scope, UNKNOWN/strict/failure policy, mẫu số, experiment
   và config; source matching `page-bbox-positive-iou-cardinality-1.0` vẫn là
   development candidate. `--print-experiment` không tạo approval.
4. Khóa cohort và baseline KIE config giống nhau cho hai Reader mode; giữ mọi
   attempted input/failure. Reader code/config thay đổi thì tạo run mới và
   review lại alignment, không gán ngược revision cho run lịch sử.

Hiện các gate này chưa đủ. Membership/hash freeze của #66 không phải reviewed
gold. Không đổi `PENDING_REVIEW` thành `VERIFIED` chỉ để lệnh trả exit 0.

## Lệnh thực tế đang được hỗ trợ

Chạy ở checkout đã tích hợp evaluator 2.2.0, Python 3.12 và dependency đã pin.
Các đường dẫn `PATH_TO_*` là đầu vào bàn giao tương lai, chưa phải artifact đã
được duyệt. Luôn dùng thư mục output mới.

Chuẩn bị/replay Reader trên validation được phép dùng:

```powershell
python -m scripts.compare_pdf_routes --manifest PATH_TO_VALIDATION/manifest.json --output results/dev/tv3-reviewed-pair-new --orientation auto
python -m scripts.verify_reader_handoff --run-dir results/dev/tv3-reviewed-pair-new --output results/dev/tv3-reviewed-contracts-new
```

Lệnh thứ hai chỉ kiểm provider/contracts, không có gold gate hoặc accuracy.
Để kiểm gói candidate #66 qua TV4 mà chưa chấm:

```powershell
python scripts/inspect_invoice_handoff.py --root PATH_TO_EXTRACTED_TV2_PACKAGE --source-revision 89281198ebaf419e511b4c99321ca3355e94fcf1 --output results/dev/tv3-tv4-unscored-new
```

Inspector trả exit 2 khi integrity/contracts đạt nhưng còn unscored; exit 1
khi có lỗi được giữ lại. Đây không phải approval hoặc benchmark failure rate.

Sau khi có **hai aligned manifests được duyệt thật**, giữ baseline KIE cố định:

```powershell
python scripts/evaluate_invoice_kie.py --manifest PATH_TO_REVIEWED/ocr-all-validation.json --grouping geometry_grouping_v2 --output results/dev/tv3-kie-ocr-all-new
python scripts/evaluate_invoice_kie.py --manifest PATH_TO_REVIEWED/route-aware-validation.json --grouping geometry_grouping_v2 --output results/dev/tv3-kie-route-aware-new
```

Các manifest cần `frozen`, `frozen_at`, `qa_status`, `verified_by`, dataset/split
provenance, configuration, sample count và gold/evidence artifact hashes đúng
hợp đồng `ai.kie.v2.evaluation.evaluate`. Evaluator trả exit 2, metrics null khi
gate/eligibility/extraction không đạt; không xuất score của tập con thành công.
Hai report phải cùng source membership và scoreable masks trước khi tính route
delta. Nếu aligned-eligible khác nhau, công bố khác biệt/mẫu số và không gọi đó
là paired source-level delta.

`--compare` của evaluator này là **KIE grouping A/B trên cùng evidence**, không
phải so sánh Reader routing. Khi TV4/lead đã duyệt grouping experiment riêng:

```powershell
python scripts/evaluate_invoice_kie.py --print-experiment
python scripts/evaluate_invoice_kie.py --manifest PATH_TO_REVIEWED/evaluator-validation-manifest.json --compare --output results/dev/tv4-grouping-ab-new
```

Không đồng thời đổi Reader routing và grouping rồi quy toàn bộ chênh lệch cho
OCR. Nếu cần cả hai yếu tố, báo ma trận Reader mode × grouping với từng config,
cùng source cohort và policy đã duyệt.

Source-level evaluation dùng [runner TV5](tv5-source-evaluation.md), sau khi có
plan/protocol, worker fingerprint, config và capture hợp lệ:

```powershell
python -m scripts.evaluate_source_backend_v2 --plan PATH_TO_REVIEWED/source-plan.json --url http://127.0.0.1:18029 --output results/dev/tv3-tv5-source-new
python -m scripts.evaluate_source_backend_v2 --plan PATH_TO_REVIEWED/source-plan.json --capture PATH_TO_RAW_BACKEND_CAPTURE --output results/dev/tv3-tv5-source-score-new
```

Chọn một trong hai: lệnh đầu chạy capture qua provider backend đang cấu hình;
lệnh sau chỉ chấm capture sẵn có. CLI không có `--reader-mode`. Muốn source-level
paired routing cần TV5 bàn giao hai provider configs/captures và approved plans
tương ứng; ZIP Reader/provider replay của #65 không tự trở thành backend capture.
Không gọi trực tiếp `source_metrics` để vượt QA/provenance gate của runner.

## Bảng kết quả cần bàn giao sau review

Lưu nguyên `report.json`, `summary.csv`, `samples.csv`, `failures.csv` của mỗi
aligned run và source reports/captures riêng. Bảng route comparison phải giữ:

- Input ID, base/family/split/condition, source hash, mode, Reader/KIE/evaluator
  revision/config, evidence/run IDs và artifact hashes.
- Intended/attempted/failed/eligible/scoreable counts; 13 header exact-match và
  P/R/F1; row detection P/R/F1; matched-cell correctness kèm mẫu số; complete
  line/header/table/invoice và coverage. Matched-cell score là conditional trên
  matched rows, cần đọc cùng row recall/complete-line, không dùng riêng.
- Source-level failure, latency từng stage và chênh lệch paired. Không lấy
  corrected/effective values hoặc tỷ lệ workflow VERIFIED làm machine accuracy.
- Ca Reader khác nhau kéo theo KIE khác nhau, kèm source, evidence polygon/text,
  expected source label và machine prediction của cả hai mode. Chỉ kết luận
  OCR propagation khi bằng chứng loại trừ thay đổi config/alignment/candidate.

Oracle-text nếu làm là nhánh QA riêng: evaluator V2 yêu cầu giữ receipt/run,
block geometry/order/confidence và engine của real evidence; chỉ thay text đã
duyệt. Điều này khác Oracle OCR legacy W2. Không sinh oracle từ KIE prediction.

Cho đến khi đủ gate, ghi **NOT_SCORED, metrics=null**, nguyên nhân và owner của
phần còn chờ. Không có final-test run hoặc kết luận accuracy trong bàn giao này.
