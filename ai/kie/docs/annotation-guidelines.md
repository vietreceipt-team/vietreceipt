# VietReceipt Annotation Guidelines for Five Core Fields

- **Status:** Ready for annotation pilot
- **Version:** 1.1
- **Owner:** Dao Minh Phuong
- **Related issue:** #1
- **Scope:** Five core receipt fields only

## 1. Purpose

Tài liệu này quy định cách con người gán nhãn ground truth cho năm field của VietReceipt. Mục tiêu là tạo annotation nhất quán, có thể audit và không làm lẫn dữ liệu OCR, nhãn người gán, dự đoán KIE hay correction trong production.

Đây không phải hướng dẫn triển khai extractor và không chứa kết quả benchmark. Keyword/regex chỉ hỗ trợ tìm candidate; annotator vẫn phải dựa vào nội dung nhìn thấy trên hóa đơn.

## 2. Annotation unit

Một annotation unit là một ảnh hóa đơn gắn với đúng một `receipt_id` và một OCR snapshot xác định bằng `ocr_run_id`.

Mỗi unit phải có đúng năm field:

1. `merchant_name`
2. `receipt_date`
3. `total_amount`
4. `invoice_id`
5. `merchant_address`

Annotation record là dữ liệu ground truth riêng. Nó không được ghi đè OCR block và không được sử dụng các tên `predicted_value` hoặc `corrected_value` để tránh nhầm với production contract.

## 3. Minimum input for annotation

Annotator cần có:

- ảnh hóa đơn gốc hoặc ảnh đã được phê duyệt cho annotation;
- `receipt_id`;
- `ocr_run_id`;
- danh sách OCR block gồm `block_id`, `text`, `polygon`, `confidence`, `reading_order`;
- field specification hiện hành;
- quyền đánh dấu trường hợp cần adjudication.

Nếu ảnh hoặc OCR snapshot không xác định được version, không bắt đầu annotation; báo lại owner để tránh tạo nhãn không truy vết được.

## 4. Annotation record shape

Mỗi field annotation có tối thiểu:

```json
{
  "field_name": "receipt_date",
  "annotation_status": "PRESENT",
  "transcribed_value": "14/08/2020",
  "normalized_value": "2020-08-14",
  "source_block_ids": ["block_2"],
  "candidate_values": [],
  "annotator_note": null
}
```

Ý nghĩa:

- `annotation_status`: quyết định của annotator theo enum chung.
- `transcribed_value`: nội dung annotator đọc trực tiếp từ ảnh, chưa normalization; không bắt buộc phải giống text OCR nếu OCR sai.
- `normalized_value`: giá trị chuẩn theo field specification; chỉ có khi status là `PRESENT` và normalization an toàn.
- `source_block_ids`: OCR block liên quan tới field. Nếu OCR bỏ sót hoàn toàn vùng chữ, để mảng rỗng và ghi rõ trong `annotator_note`.
- `candidate_values`: các candidate hợp lý khi status là `AMBIGUOUS`; không chọn ngẫu nhiên một candidate làm ground truth.
- `annotator_note`: giải thích ngắn cho ngoại lệ, disagreement hoặc OCR omission; không chép dữ liệu nhạy cảm không cần thiết.

Ground-truth annotation không có `confidence`. Confidence là output của OCR/KIE, không phải độ chắc chắn giả do annotator tự đặt.

## 5. General annotation principles

1. Chỉ gán những gì nhìn thấy hoặc đọc được từ ảnh.
2. Không tìm tên cửa hàng, địa chỉ hoặc mã doanh nghiệp trên Internet để bổ sung phần ảnh thiếu.
3. Không tự sửa chính tả tên riêng nếu ảnh không cung cấp đủ bằng chứng.
4. Không lấy OCR text làm ground truth một cách máy móc; luôn đối chiếu ảnh.
5. Không dùng chuỗi rỗng, `N/A`, `không có`, `null string` hay giá trị giả thay cho JSON `null`.
6. Không ép một field thành `PRESENT` chỉ vì regex tìm thấy candidate.
7. Không chọn amount lớn nhất nếu chưa xác định được vai trò của amount.
8. Không chọn mã dài nhất làm invoice ID nếu chưa xác định được nhãn/ngữ cảnh.
9. Khi không đủ bằng chứng, giữ uncertainty bằng `AMBIGUOUS`, `UNREADABLE` hoặc `UNKNOWN`.
10. Mọi ngoại lệ có thể ảnh hưởng rule/model phải được ghi chú và đưa vào adjudication log.

## 6. Status decision rules

### `PRESENT`

Dùng khi field xuất hiện trên hóa đơn, đọc được đủ nội dung và annotator xác định được một giá trị chính theo specification.

Yêu cầu:

- `transcribed_value` khác `null` và không rỗng;
- `normalized_value` đúng canonical type;
- thông thường có ít nhất một `source_block_id`;
- `candidate_values` để rỗng.

### `NOT_PRESENT`

Dùng khi annotator đã kiểm tra toàn bộ ảnh và xác nhận field không xuất hiện.

Yêu cầu:

- `transcribed_value=null`;
- `normalized_value=null`;
- `source_block_ids=[]`;
- không dùng khi OCR bỏ sót nhưng chữ vẫn xuất hiện trên ảnh.

### `UNREADABLE`

Dùng khi có bằng chứng về vị trí/nhãn của field nhưng ký tự cần thiết không thể đọc đáng tin cậy do mờ, chói, crop, gấp giấy hoặc hư hỏng.

Yêu cầu:

- `normalized_value=null`;
- `source_block_ids` chứa block liên quan nếu OCR tạo được block;
- `transcribed_value` chỉ chứa phần đọc chắc chắn nếu annotation format cho phép partial transcription; không biến phần đoán thành ground truth;
- ghi nguyên nhân trong `annotator_note`.

### `AMBIGUOUS`

Dùng khi có từ hai candidate hợp lý trở lên hoặc một candidate có nhiều cách diễn giải hợp lệ.

Ví dụ:

- có hai ngày nhưng không xác định được ngày giao dịch;
- có cả tổng trước giảm giá và tổng sau giảm giá nhưng nhãn bị cắt;
- có nhiều mã cùng được in cạnh nhãn không rõ nghĩa.

Yêu cầu:

- `normalized_value=null`;
- lưu candidate đã nhìn thấy trong `candidate_values`;
- lưu các `source_block_ids` liên quan;
- ghi lý do ngắn trong `annotator_note`.

### `UNKNOWN`

Dùng khi chưa đủ thông tin để kết luận field vắng mặt, unreadable hay ambiguous; hoặc annotation input bị thiếu thành phần cần thiết.

Yêu cầu:

- `normalized_value=null`;
- giải thích nguyên nhân trong `annotator_note`;
- chuyển sang adjudication nếu có thể giải quyết bằng kiểm tra dữ liệu nguồn.

## 7. Annotation workflow

### Step 1 — Verify the unit

- Kiểm tra ảnh mở được và đúng `receipt_id`.
- Kiểm tra OCR blocks thuộc đúng `ocr_run_id`.
- Không annotation ảnh trùng hoặc ảnh không phải hóa đơn mà không đánh dấu dataset issue.

### Step 2 — Read the complete receipt

Quan sát toàn bộ header, body và footer trước khi chọn candidate. Việc chỉ xem các dòng regex match dễ nhầm subtotal, mã sản phẩm hoặc địa chỉ khách hàng.

### Step 3 — Locate candidates

- Dùng keyword/regex seed để hỗ trợ tìm kiếm nếu cần.
- Đối chiếu keyword, vị trí, reading order và nội dung xung quanh.
- Lưu tất cả block tạo thành candidate, kể cả field trải trên nhiều dòng.

### Step 4 — Assign status

Áp dụng thứ tự câu hỏi:

1. Field có xuất hiện trên ảnh không?
2. Nếu có, đọc được đầy đủ không?
3. Nếu đọc được, có đúng một candidate chính không?
4. Nếu có một candidate, normalization có an toàn không?

Không mặc định `NOT_PRESENT` khi câu trả lời cho bước đầu tiên chưa chắc chắn.

### Step 5 — Transcribe

- Chép đúng nội dung nhìn thấy.
- Giữ dấu tiếng Việt nếu nhìn thấy rõ.
- Giữ số 0 đầu của invoice ID.
- Không chèn ký tự OCR đã bỏ sót nếu ảnh cũng không đọc được.

### Step 6 — Normalize

- Áp dụng đúng rule của field specification.
- Không tự suy năm thiếu, currency khác hoặc địa danh bị cắt.
- Nếu rule không giải quyết được chắc chắn, giữ `normalized_value=null` và đổi status phù hợp.

### Step 7 — Link evidence

- Chọn tất cả OCR blocks trực tiếp tạo nên field.
- Không chọn block keyword nếu keyword không phải một phần giá trị, trừ khi UI/annotation tool có trường evidence riêng.
- Nếu OCR bỏ sót chữ nhưng annotator đọc được từ ảnh, để `source_block_ids=[]` và ghi `OCR_OMISSION` trong note.

### Step 8 — Self-review

Chạy checklist cuối tài liệu trước khi submit annotation.

## 8. Field-specific quick rules

### Merchant name

- Ưu tiên customer-facing brand ở header.
- Nếu có cả brand và legal entity, chọn brand; chỉ dùng legal entity khi không có brand.
- Không chọn tên khách hàng, ngân hàng hoặc cổng thanh toán.
- Nếu sau khi áp dụng thứ tự ưu tiên vẫn không xác định được người bán chính, dùng `AMBIGUOUS` và đưa vào adjudication.

### Receipt date

- Chọn ngày giao dịch/bán hàng/thanh toán theo ngữ cảnh.
- Không chọn hạn đổi trả hoặc ngày chương trình thành viên.
- Canonical form là `YYYY-MM-DD`.
- Nhãn giao dịch tiếng Việt cho phép áp dụng rule `DD/MM/YYYY`; nếu không có bằng chứng locale, chỉ normalize khi calendar cho phép đúng một thứ tự.
- Không tự suy năm bị thiếu. Năm hai chữ số luôn dùng `AMBIGUOUS`, `normalized_value=null` và đưa vào review trong v1.

### Total amount

- Chọn số tiền cuối cùng khách phải thanh toán.
- Không chọn subtotal, discount, cash received hoặc change.
- Canonical form là JSON integer VND.
- Không tự quy đổi currency.

### Invoice ID

- Ưu tiên invoice/receipt number, sau đó mới cân nhắc transaction/reference number.
- Không chọn tax ID, phone number, product barcode hoặc terminal ID.
- Luôn lưu dạng string và giữ số 0 đầu.

### Merchant address

- Chọn địa chỉ cửa hàng/chi nhánh phát hành hóa đơn.
- Không chọn địa chỉ khách hàng hoặc địa chỉ giao hàng.
- Ghép các dòng theo reading order; không bổ sung địa danh không xuất hiện.

## 9. Disagreement and adjudication

Trong annotation pilot, các trường hợp sau phải được chuyển cho KIE Owner hoặc annotator thứ hai:

- hai annotator chọn status khác nhau;
- hai normalized values khác nhau;
- khác nhau về block evidence làm thay đổi candidate;
- brand/legal entity conflict;
- transaction date/invoice date conflict;
- total/subtotal conflict;
- invoice ID/reference number conflict.

Adjudicator phải ghi:

- giá trị ban đầu của từng annotator;
- quyết định cuối;
- lý do;
- rule/specification section được áp dụng;
- đề xuất cập nhật guideline nếu trường hợp chưa được bao phủ.

Không sửa im lặng annotation cũ mà không lưu audit record.

## 10. Privacy and dataset hygiene

- Không commit ảnh hóa đơn thật hoặc dữ liệu cá nhân nhạy cảm vào repository nếu chưa được phép.
- Example trong Git phải là synthetic/illustrative hoặc đã được khử định danh.
- Không lưu access token, signed image URL hoặc thông tin đăng nhập trong annotation.
- Raw dataset giữ ở storage/dataset location được nhóm chấp thuận; Git chỉ lưu script, schema, manifest an toàn và tài liệu.

## 11. Annotation completion checklist

- [ ] Đúng `receipt_id` và `ocr_run_id`.
- [ ] Có đúng năm canonical fields.
- [ ] Mỗi field có một status hợp lệ.
- [ ] `PRESENT` có transcribed và normalized value đúng type.
- [ ] Non-`PRESENT` có `normalized_value=null`.
- [ ] Không dùng chuỗi giả thay cho `null`.
- [ ] Invoice ID vẫn là string và giữ số 0 đầu.
- [ ] Total là integer VND khi `PRESENT`.
- [ ] Date theo `YYYY-MM-DD` khi `PRESENT`.
- [ ] Source block IDs thuộc đúng OCR run hoặc có note `OCR_OMISSION`.
- [ ] Không có nội dung suy đoán từ nguồn bên ngoài ảnh.
- [ ] Trường hợp mơ hồ đã có candidate/note hoặc được đưa vào adjudication.

## 12. Pending owner confirmations

- **NOTE — OCR Owner:** xác nhận polygon, coordinate convention, reading order và tính duy nhất của `block_id`.
- **NOTE — Backend Owner:** mirror rule `review_reasons` không rỗng khi machine review là true trong shared schema.
- **DECIDED — KIE Owner:** v1 không suy luận năm hai chữ số; mọi policy tương lai phải có version mới và contract tests.
- **DECIDED — KIE Owner:** ưu tiên customer-facing brand, chỉ dùng legal entity khi không có brand; annotation pilot dùng để thu thập edge case, không thay đổi ngầm policy.
