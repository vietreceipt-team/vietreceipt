# TV5: original-file capture → source-spatial evaluation

Bàn giao nối TV4 PR #69 (đồng bộ đến `1e7b407`, evaluator `invoice-evaluation-2.2.0`) vào TV5. Kết quả QA/accuracy thật vẫn chờ người phụ trách. Tài liệu này cập nhật phần phụ thuộc TV4 trong [báo cáo PR #67](tv5-progress-20261023.md), không thay đổi các run lịch sử hoặc tự duyệt gold.

## Đã tích hợp

- `scripts/evaluate_source_backend_v2.py`: một lệnh gate plan → HTTP upload/Redis/Celery → chọn immutable OCR/KIE của attempt → gọi `source_metrics`. Không chạy lại KIE trên OCR dựng sẵn, không đọc effective/corrected values để chấm máy.
- `scripts/prepare_tv2_source_plan.py`: chuyển gói TV2 train/validation thành plan **PENDING_REVIEW**. Copy source/gold/row-region nguyên byte, giữ hash và alias sample/receipt nguồn; không đặt OCR block IDs hoặc reviewer giả. Chỉ validation được đưa vào cohort chạy; registry train dùng để kiểm tra leakage.
- `schemas/backend-source-evaluation.v1.schema.json`: hợp đồng TV5 riêng cho source runner. Không nhầm với experiment schema A/B của evaluator KIE. Grouping mặc định vẫn `geometry_grouping_v2`, `invoice-baseline/2.1.0`; không bật variant `column_interval_grouping_v2_1` làm production default.
- Worker lưu SHA-256/content type/số byte của nguồn thực sự đọc trong `attempt.provenance.source`, cả kết thúc success/failure. Attempt chưa đọc nguồn hoặc worker chết trước khi lưu có `source=null`. Không backfill hoặc sửa các attempt cũ.
- OCR CI cài thêm dependency PDF test đã pin. Lỗi đỏ ở PR #69 là test Reader mới được discover nhưng thiếu `reportlab`; không bỏ test để làm xanh CI.

## Chuẩn bị bàn giao QA

Sau khi lấy ZIP TV2 ở revision đã chỉ định và kiểm tra SHA-256:

```sh
python -m scripts.prepare_tv2_source_plan \
  --root /path/to/extracted-tv2-handoff \
  --output results/tv5-source-plan-001 \
  --source-revision 8a603300071d6dbfebd23e8f22a8c9cbac90ff48
```

`plan.pending.json` có 20 source validation từ 5 base, một family table_heavy, cùng registry 80 train/validation. Các reviewer/date/protocol approvals và worker fingerprint chưa chốt để null. Gold và source regions của TV2 vẫn là candidate. Giá trị/page size được lấy từ nguồn để chuẩn bị kiểm tra, không phải duyệt nhãn/vùng đúng.

Người chịu trách nhiệm cần review thực tế và tạo **bản plan mới** theo schema:

1. TV2 + reviewer độc lập kiểm source gold/regions; `reviewed_by` khác `annotated_by`, thời gian có timezone, hash duyệt gắn đúng source/gold/regions. Source gold dùng OCR IDs rỗng; không đổi source value theo prediction. Original source sample/receipt IDs nằm trong `source_sample_id`/`source_receipt_id`; server receipt ID khác được ràng buộc bằng byte hash, không sửa gold để ép UUID trùng.
2. TV1/TV2/TV4/TV5 ghi đồng thuận protocol: evaluator/matching version, UNKNOWN policy, scope 13 headers + line items, tax excluded, positive-IoU matching, coordinate profile và configuration cụ thể. `approved_by`/date là khai báo từ con người; phần mềm không xác thực danh tính người ký và không tạo phê duyệt thay họ.
3. Freeze worker implementation fingerprint từ `attempt.provenance.runtime.source_sha256` của runtime được chọn, cùng reader config và KIE config. Hash này bao gồm source AI/backend/schema; runner/scorer có commit/hash riêng. Các run cũ chưa lưu worker source hash per input không được suy diễn là đã có binding mới.

Không chỉ sửa `PENDING_REVIEW` thành `VERIFIED` để vượt gate. KIE experiment A/B dùng declaration chính xác từ `python scripts/evaluate_invoice_kie.py --print-experiment`; nó không cấp quyền source benchmark. Kernel positive-IoU là đề xuất có version, chưa phải final protocol được nhóm co-sign.

## Chạy và xuất kết quả

Dùng Python 3.12 và dependency đã pin như [hướng dẫn runtime](v2-reproducible-demo.md). Khi plan được duyệt thật và API/worker dùng đúng fingerprint/config:

```sh
python -m scripts.evaluate_source_backend_v2 \
  --plan /path/to/reviewed-plan.json \
  --output results/tv5-source-run-001 --url http://127.0.0.1:18029
```

Nếu có raw capture tương thích, chấm riêng, không HTTP hoặc inference thêm:

```sh
python -m scripts.evaluate_source_backend_v2 \
  --plan /path/to/reviewed-plan.json --capture /path/to/raw-capture \
  --output results/tv5-source-score-001
```

Thư mục mới mỗi lần. Gate thiếu/không hợp lệ trả exit 2, `metrics=null`, `evaluated=0`, reason code không chứa raw exception text/URL/PII. Gate không vượt qua thì lệnh một bước không upload. Stage source capture giữ mọi missing/hash/timeout/worker failure trong intended cohort. File gold/regions hoặc sample/capture thiếu khiến **toàn bộ score bị chặn**, không xuất accuracy trên tập còn lại đẹp hơn. Source file mất khi chạy là input failure có record riêng, khác với missing gold không thể chấm.

`capture/` giữ machine JSONL, worker source hash/commit/runtime, timing, failure CSV và system metrics như PR #67. `source-evaluation/` có report JSON, per-sample JSON/CSV và failures CSV. Lỗi đủ điều kiện được truyền `None` vào kernel; vẫn giữ gold trong mẫu số, kể cả lease-expired/storage failure không có prediction. Client processing deadline là thất bại của lượt đo, không tự hủy job hoặc dùng output tới sau deadline để sửa điểm. Không gộp reviewed exports vào machine accuracy. UNKNOWN được mask và các document strict chưa đủ nhãn cho kết quả null; tax groups không được chấm.

## Ràng buộc identity và hình học

- Input hash trong plan, capture manifest, result và **worker đọc source** phải khớp cho mẫu thành công. Receipt/attempt/OCR/KIE IDs phải liên kết đúng selected run; config và worker source fingerprint khớp protocol. Failed attempt kiểm identity/failure code và giữ trường hợp chưa đọc được source là failure, không bịa hash.
- Ảnh dùng normalized top-left của hình **sau EXIF transpose**, trước OCR rotation/resize; TV3 phải phục hồi polygon về frame này. PDF dùng crop/unrotated frame (`page.set_rotation(0)`) và DPI của reader. So sánh page count, canonical page size của source, frozen geometry và evidence; từ chối frame không đúng, không đoán phép xoay/tịnh tiến từ prediction/gold.
- `source_metrics` chỉ lấy vùng nguồn độc lập và block polygon của **prediction thật** để match tối đa one-to-one theo positive area IoU. Không lấy gold block IDs để đẩy vào output. Geometry/IoU gate không chứng minh vùng gold đã được người độc lập kiểm tra — việc đó vẫn cần QA.
- Final/test/benchmark split hiện bị khóa trong runner source phiên bản này. Final execution cần bản freeze/gate được lead nghiệm thu, không được mở chỉ vì test phần mềm hoặc development run thành công.

## Bằng chứng và giới hạn

Software regression dùng PDF giả với expected text/rows định nghĩa độc lập và approval **test doubles**, không phải đồng ký của nhóm. Kiểm HTTP → canonical Reader/KIE → raw source metrics; lỗi identity/hash/config/split/geometry, UNKNOWN/strict, expired worker/storage/reader failure, one-command gate và không ghi đè artifact. Test có EXIF orientation và PDF intrinsic rotation. Baseline fingerprints của TV4 vẫn được chạy; variant không tự thành default.

Gói TV2 thật 20 mẫu đã được chuẩn bị pending và thử gate: exit 2, metrics null, không upload/score khi chưa QA. Test/CI xanh không phải bằng chứng final accuracy. Các capture PR #67 vẫn có giá trị kiểm chứng workflow nhưng thiếu field worker input hash mới sẽ không được tự nâng cấp thành run đủ điều kiện source-scoring.

Paddle Linux ARM64 vẫn có SIGSEGV đã ghi; lớp subprocess và recipe native/AMD64 giữ nguyên. Đợt này không sửa OCR hoặc hứa cải thiện chất lượng/latency. Source-region policy và sign-off, source QA độc lập, mock cuối và final freeze vẫn cần chủ sở hữu nghiệm thu.


Bàn giao mới nhất và kiểm tra dependency/JSON/CSV: [validation 24/10/2026](tv5-source-validation-20261024.md).
