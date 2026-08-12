# KIE VietReceipt

Module KIE nhận OCR output đã chuẩn hóa, chọn và chuẩn hóa năm field nghiệp vụ của hóa đơn. Tuần 1 chỉ khóa specification, annotation rules, data model và seed rules; chưa triển khai extractor và chưa có benchmark result.

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

## Input contract

KIE nhận một immutable OCR run gồm:

- `receipt_id` và `ocr_run_id`;
- OCR engine name/version;
- image width/height;
- OCR blocks có `block_id`, `text`, `polygon`, `confidence`, `reading_order`.

KIE input contract dùng polygon bốn điểm normalized theo thứ tự top-left, top-right, bottom-right, bottom-left trên ảnh sau EXIF orientation; `reading_order` là integer duy nhất, zero-based trong OCR run. KIE Owner đã chấp nhận representation này; OCR Owner và shared OCR schema vẫn phải xác nhận/enforce trước khi freeze contract chung. KIE không phụ thuộc trực tiếp vào raw object của một OCR engine cụ thể.

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
- `/openapi/openapi.yaml`
- `/docs/integration-contracts.md`
- `/docs/receipt-state-machine.md`

Không tạo schema KIE thứ hai trong module này. Contract conflict phải được xử lý bằng Issue/PR chung với Backend, OCR và Frontend.

## Data integrity rules

- Không tự bịa field value, confidence hoặc benchmark metric.
- Không ghi đè OCR raw, prediction hoặc normalization bằng correction.
- JSON `null` biểu diễn giá trị không có; không dùng chuỗi `N/A` hoặc chuỗi rỗng.
- Non-`PRESENT` phải có `normalized_value=null`.
- `PRESENT` phải có ít nhất một source block thuộc `source_ocr_run_id`.
- `machine_needs_review=true` phải có ít nhất một versioned review reason code.
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
