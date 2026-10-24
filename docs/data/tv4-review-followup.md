# TV2 xử lý yêu cầu TV4 ngày 24/10/2026

## Yêu cầu có nghĩa gì?

TV4 đã replay 80 evidence của TV2 qua hai cấu hình. Đó là kiểm tra đầu vào/đầu ra
hợp contract, chưa chứng minh source gold, vùng nguồn hoặc block alignment đúng.
Muốn chấm A/B cần duyệt thật các nhãn/vùng/liên kết và manifest hợp evaluator 2.2.0.
Freeze hiện tại chỉ khóa thành viên và hash, không cấp VERIFIED.

TV4 đã publish [PR #69](https://github.com/vietreceipt-team/vietreceipt/pull/69),
head kiểm tra `1e7b407d1314110ce2d8411211f55f49f7eb0ffd`.
Thông tin cũ “chưa publish evaluator” được thay thế bằng kết quả kiểm tra này.
Không merge code của TV4 vào nhánh data; dùng snapshot riêng để kiểm tra.

## TV2 đã làm

- Lấy experiment trực tiếp bằng `--print-experiment`, validate schema của TV4.
- Baseline `geometry_grouping_v2`, config `invoice-baseline/2.1.0`.
- Variant `column_interval_grouping_v2_1`, config `invoice-column-intervals/2.2.0`.
  Không dùng placeholder `relation_grouping_v2_1` trong manifest evaluator mới.
- Chuẩn bị evaluator manifests train 60/validation 20 với provenance, counts,
  freeze timestamp, baseline anchor và experiment chính xác. Giữ PENDING_REVIEW,
  cấu hình/experiment chờ đồng ký; không đưa final test vào.
- Chuẩn bị 80 phiếu review riêng, ràng buộc hash source/source gold/source regions/
  source rows/evidence/aligned candidate; tên và ngày để trống vì chưa có review thật.
- Công cụ kiểm tra phiếu từ chối tự review, thiếu approval, ngày không timezone,
  stale/substituted artifacts và thay nhãn chưa được owner duyệt. Không cấp VERIFIED.
- Replay lại 80/80 evidence qua hai cấu hình bằng code PR #69: pass contract,
  không chạy lại OCR, không chấm accuracy. Giữ nguyên package v1, source và IDs.
- Chạy evaluator A/B trên validation manifest mới: exit 2, metrics/delta null vì
  chưa được duyệt. Đây là kiểm tra gate hoạt động, chưa phải kết quả đạt QA.

## Gói và lệnh sử dụng

Giải nén `data/handoffs/tv4-dev-v1.zip`, rồi giải nén
`data/handoffs/tv4-evaluation-intake-v2.zip` **vào cùng thư mục gốc đó**.
Overlay chỉ thêm manifest evaluator/experiment/phiếu review; không thay source,
evidence hoặc gold v1. Dùng `evaluator-train-manifest.json` và
`evaluator-validation-manifest.json` cho evaluator mới; hai candidate manifests
cũ được giữ để kiểm tra nguồn gốc, không dùng làm scored input.

Để tái tạo, dùng checkout riêng của TV4 đúng commit trên và Python 3.12 với
dependencies requirements-contracts.txt/requirements-data.txt:

```powershell
python -m scripts.data.prepare_tv4_evaluation --root PATH_TO_V1 --runtime PATH_TO_TV4_CHECKOUT --output NEW_INTAKE_DIRECTORY
python -m scripts.data.check_tv4_reviews --root NEW_INTAKE_DIRECTORY --output NEW_REVIEW_REPORT.json
```

Lệnh review hiện trả exit 2 với 0/80 phiếu hoàn tất. Exit 0 chỉ cho biết phiếu
đủ cấu trúc/hash, không chứng minh đã có con người review hay cấp quyền VERIFIED.

Chạy trong checkout TV4, dùng đường dẫn tuyệt đối tới intake:

```powershell
python -m unittest tests.test_kie_v2_evaluation tests.test_kie_v2_grouping tests.test_kie_v2_source_evaluation -v
python scripts/evaluate_invoice_kie.py --manifest PATH_TO_INTAKE/evaluator-validation-manifest.json --compare --output NEW_RESULT_DIRECTORY
```

Khi chưa QA, lệnh evaluator phải exit 2 và không có accuracy. Không sửa status
để làm lệnh pass. Báo cáo kiểm tra nằm trong `docs/data/tv4-verification/20261024/`.

## Ai phải làm phần còn lại?

| Việc | Người phụ trách cần phối hợp | Kết quả cần có |
| --- | --- | --- |
| Đọc source và xác nhận nhãn/vùng nguồn | TV2 + reviewer độc lập do lead phân công | Tên người tạo nhãn/reviewer, ngày thật, approval và hash đúng artifact |
| Kiểm tra liên kết block | TV2 + reviewer; TV3 hỗ trợ OCR/geometry | Duyệt từng ID thực, giữ unresolved khi OCR mất nội dung; không đổi source label |
| Chốt version Reader | TV3 | Xác nhận version/config/log chính thức; code mới có cần rerun không |
| Chốt status/mẫu số và spatial policy | TV1 + TV2 + TV4 + TV5 | Đồng ký protocol; positive-IoU tie, geometry transforms và failure policy |
| Duyệt experiment/config và chạy scored A/B | TV1/TV4 sau QA | Baseline/variant đúng schema; precision/cell/strict/coverage trước khi chọn default |
| Thay #60 bằng #66, chọn SROIE | Lead/TV1 | Quyết định rõ; không tự đóng PR hoặc issue |
| Source-level runner | TV5 cùng TV4 | Kiểm source identity/hash/coordinate transforms, failed input vẫn giữ cohort |
| Mock độc lập và final freeze | Lead phân công người thiết kế/annotate/reviewer khác | Bộ unseen độc lập, QA rồi mới freeze cấu hình/test và final run |

## Lập trường TV2 đề xuất để đồng ký

TV2 đề xuất UNKNOWN không vào value metrics; NOT_PRESENT/UNREADABLE/AMBIGUOUS
vẫn chấm status+null; strict chỉ đạt khi mọi ô cần chấm đều known và đúng.
Complete-invoice hiện gồm 13 headers và line items, chưa gồm tax groups.
Đây là đề xuất phía TV2, không ký thay TV1/TV4/TV5. Spatial policy còn chờ thống nhất.

Nếu Reader/alignment lỗi: giữ record trong inventory và lý do lỗi. Không loại
record để tăng điểm, không gán NOT_PRESENT cho chữ bị OCR bỏ sót. Cohort chấm aligned
và source-level phải khai báo rõ; không coi shared-evidence là end-to-end.
Không thay selected-value text hoặc tạo oracle trước QA riêng.

**Chưa hoàn thành nghiệm thu #47:** cần người độc lập review, protocol/config
sign-off, quyết định nguồn dữ liệu và bộ mock/final evaluation đúng quy trình.
