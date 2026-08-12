# KIE VietReceipt

Module KIE nhận OCR output theo shared schema đã chuẩn hóa về cấu trúc, sau đó chọn, diễn giải và chuẩn hóa năm field nghiệp vụ của hóa đơn. Tuần 1 chỉ khóa specification, annotation rules, data model và seed rules; chưa triển khai extractor và chưa có benchmark result.

## Owner

- Dao Minh Phuong — KIE & Data Engineering
- Related GitHub Issue: #1

## Five canonical fields

- `merchant_name` — tên cửa hàng/người bán
- `receipt_date` — ngày giao dịch, canonical `YYYY-MM-DD`
- `total_amount` — tổng tiền thanh toán, non-negative integer VND
- `invoice_id` — mã hóa đơn/giao dịch, luôn là string
- `merchant_address` — địa chỉ cửa hàng/chi nhánh

Không dùng alias như `merchant`, `date`, `total` hoặc `address` qua interface giữa các module.

## Week 1 deliverables

- [`docs/field-specification.md`](docs/field-specification.md): định nghĩa, include/exclude, candidate selection, normalization và missing-value handling của năm field.
- [`docs/annotation-guidelines.md`](docs/annotation-guidelines.md): quy trình gán nhãn, status rules, adjudication và quality checklist.
- [`docs/data-model.md`](docs/data-model.md): production/annotation data model và ER diagrams.
- [`resources/keyword-regex-seed.yaml`](resources/keyword-regex-seed.yaml): keyword/regex seed chưa benchmark; chỉ dùng tạo candidate.
- [`examples/annotation-record.example.json`](examples/annotation-record.example.json): synthetic annotation example, không phải dataset/model output.

Runtime KIE schema không được nhân bản trong `ai/kie/`. Shared schema tại root repository là source of truth duy nhất cho integration contract.

## Input contract

KIE nhận một immutable OCR run gồm:

- `receipt_id` và `ocr_run_id`;
- OCR engine name/version;
- image width/height;
- OCR blocks có `block_id`, `text`, `polygon`, `confidence`, `reading_order`.

KIE input contract dùng polygon bốn điểm normalized theo thứ tự top-left, top-right, bottom-right, bottom-left trên ảnh sau EXIF orientation; `reading_order` là integer duy nhất, zero-based trong OCR run. KIE Owner chấp nhận representation này ở phía consumer; OCR Owner và shared OCR schema vẫn phải xác nhận/enforce khả năng sản xuất đúng representation trước khi contract chung được freeze. KIE không phụ thuộc trực tiếp vào raw object của một OCR engine cụ thể và không được sửa OCR text/block đã lưu.

## KIE-owned output

Một KIE run trả đúng năm canonical fields. Machine-owned attributes gồm:

- `raw_text`;
- `predicted_value`;
- `normalized_value`;
- `value_status`;
- `confidence`;
- `machine_needs_review`;
- `review_reasons`;
- `source_block_ids`.

KIE output được version bằng `kie_run_id`, extractor name/version và `source_ocr_run_id`. Reprocess tạo run mới; không overwrite run cũ.

`source_block_ids` trong runtime contract là provenance/evidence trực tiếp cho quyết định KIE. `raw_text` được ghép nguyên văn từ các block này theo `reading_order`. Nếu trong tương lai UI cần phân biệt block chứa giá trị và block chỉ cung cấp ngữ cảnh/nhãn, thay đổi đó phải đi qua shared contract thay vì tự thêm field trong module KIE.

## Backend-owned layers

KIE không tạo:

- `corrected_value` hoặc `corrected_status`;
- `has_correction`;
- `effective_value` hoặc `effective_status`;
- `effective_needs_review`;
- correction history.

Backend giữ các lớp này tách khỏi machine output. `effective_value` chỉ dùng correction/normalization khi effective status là `PRESENT`; mọi non-`PRESENT` effective status có value `null`. Giá trị hiệu lực không fallback sang `predicted_value`.

## Shared sources of truth

Sau khi Backend contract v1.3 được merge:

- `/schemas/ocr-result.schema.json`
- `/schemas/kie-result.schema.json`
- `/schemas/annotation-record.schema.json`
- `/openapi/openapi.yaml`
- `/docs/integration-contracts.md`
- `/docs/receipt-state-machine.md`

Không tạo schema KIE thứ hai trong module này. Contract conflict phải được xử lý bằng Issue/PR chung với Backend, OCR và Frontend.

## Ground-truth boundary

Ground-truth annotation là dữ liệu semantic ở mức receipt/field và không được coi là prediction của OCR/KIE. `source_ocr_run_id` cùng `source_block_ids` chỉ là alignment metadata phục vụ audit và error analysis cho snapshot OCR đang dùng trong annotation pilot.

Nếu thay OCR engine hoặc tạo OCR run mới, semantic label như `total_amount=113000` không tự thay đổi chỉ vì block ID thay đổi. Trường hợp OCR omission phải được ghi chú rõ thay vì biến lỗi OCR thành ground truth.

## Data integrity rules

- Không tự bịa field value, confidence hoặc benchmark metric.
- Không ghi đè OCR raw, prediction hoặc normalization bằng correction.
- JSON `null` biểu diễn giá trị không có; không dùng chuỗi `N/A` hoặc chuỗi rỗng.
- Non-`PRESENT` phải có `normalized_value=null`.
- `PRESENT` phải có ít nhất một source block thuộc `source_ocr_run_id` trong runtime KIE output.
- `machine_needs_review=true` phải có ít nhất một review reason code thuộc enum shared contract và có `review_policy_version`.
- `raw_text` ghép nguyên văn source blocks theo `reading_order` bằng `\n`.
- Rule-based inference phải có version và test.
- V1 không suy luận năm hai chữ số; trường hợp này là `AMBIGUOUS` và normalized value `null`.
- Keyword/regex match chỉ tạo candidate, không tự quyết định ground truth.
- Không commit ảnh hóa đơn thật hoặc dữ liệu nhạy cảm chưa được phép.

## Pending external sign-off

- **OCR Owner:** polygon, coordinate convention, `block_id`, `reading_order` và source-block linkage.
- **Frontend Owner:** dữ liệu đủ cho highlighting và dùng `effective_needs_review` trong UI.
- **Backend Owner:** effective projection, correction audit và concurrency strategy.
- **DevOps Owner:** private storage, queue và secrets policy.

Không đánh dấu các mục này hoàn thành thay owner tương ứng.
