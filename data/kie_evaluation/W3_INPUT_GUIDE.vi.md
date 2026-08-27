# Hướng dẫn nhập liệu W3 OCR + KIE

Tài liệu này đi cùng Issue #30. Workspace đã có sẵn 40 Real OCR hợp lệ,
80 phiếu annotation trống (A/B), 40 Oracle OCR draft và 40 phiếu Oracle QA
trống. Không file trống nào được coi là gold hoặc `VERIFIED`.

## 1. Phân công bắt buộc

- Annotator A và annotator B phải là **hai người khác nhau**.
- B phải hoàn thành phiếu của mình mà không xem phiếu A và không xem KIE
  prediction.
- Adjudicator phải khác A và B.
- Người chuẩn bị Oracle và người review Oracle phải khác nhau.
- Không một người nào tự điền cả A, B và adjudication cho cùng receipt.

Nếu bạn là người nhập liệu theo phân công của leader, hãy xác nhận mình đang
làm vai trò nào trước khi sửa file: annotator A, annotator B, Oracle preparer
hay Oracle reviewer.

## 2. File cần mở cho mỗi receipt

Cách thuận tiện nhất cho annotator A là chạy GUI prediction-free:

```powershell
.\.venv\Scripts\python.exe scripts\annotate_kie.py `
  --slot a `
  --annotator-id ngbinhminhdev-blip
```

GUI tự mở receipt chưa hoàn thành đầu tiên, hiển thị ảnh có polygon/`block_id`,
danh sách Real OCR block và form đúng năm field. `Ctrl+S` lưu nháp;
`Ctrl+Enter` chỉ lưu hoàn thành khi schema và liên kết block đều hợp lệ. Có thể
mở thẳng một receipt bằng `--test-id R002`.

Ví dụ `R001`:

| Mục đích | File |
|---|---|
| Ảnh nguồn | `data/test_set/images/R001.jpg` |
| Real OCR và danh sách block | `results/ocr_outputs/R001.json` |
| Phiếu annotator A | `data/kie_annotations/annotator_a/R001.json` |
| Phiếu annotator B | `data/kie_annotations/annotator_b/R001.json` |
| Oracle draft | `data/kie_oracle_ocr/drafts/R001.json` |
| Phiếu QA Oracle | `data/kie_oracle_ocr/qa/R001.json` |

Làm tương tự từ `R001` đến `R040`. Không sửa `receipt_id`,
`source_ocr_run_id` hoặc `annotation_id` đã được tạo sẵn.

## 3. Cách điền phiếu annotation A hoặc B

Điền metadata trước:

- `data_provenance`: mô tả ảnh/snapshot và cách annotation;
- `annotator_id`: ID thật, ổn định của người gán nhãn;
- `annotated_at`: thời gian ISO 8601, ví dụ `2026-08-26T14:30:00+07:00`.

Sau đó đọc **toàn bộ ảnh** và điền đúng năm field:

1. `merchant_name` — tên/brand cửa hàng;
2. `receipt_date` — ngày giao dịch, chuẩn hóa `YYYY-MM-DD`;
3. `total_amount` — tiền cuối cùng khách trả, JSON integer VND;
4. `invoice_id` — string, giữ nguyên số 0 ở đầu;
5. `merchant_address` — địa chỉ chi nhánh trên hóa đơn.

### Khi field có một giá trị rõ ràng

```json
{
  "field_name": "total_amount",
  "annotation_status": "PRESENT",
  "transcribed_value": "113,000",
  "normalized_value": 113000,
  "currency": "VND",
  "source_block_ids": ["block_N"],
  "candidate_values": [],
  "annotator_note": null
}
```

`block_N` ở trên chỉ là ký hiệu minh họa. Phải thay bằng ID thực tế trong
`results/ocr_outputs/Rxxx.json`.

### Block không phải nhãn 0/1

`block_0`, `block_1`, `block_2`... là các vùng chữ OCR theo thứ tự đọc, không
phải lựa chọn nhị phân cho cả ảnh. Với mỗi field, `source_block_ids` chứa mọi
block thực sự tạo nên giá trị đó. Một field có thể dùng một hoặc nhiều block.

Nếu chữ nhìn rõ trên ảnh nhưng Real OCR bỏ sót hoàn toàn:

```json
"source_block_ids": [],
"annotator_note": "OCR_OMISSION: mô tả ngắn vùng chữ bị bỏ sót"
```

Không được bịa một `block_id` không tồn tại.

### Các status còn lại

- `NOT_PRESENT`: đã xem toàn ảnh và field thật sự không có; các value là
  `null`, block/candidate để `[]`.
- `UNREADABLE`: thấy field nhưng không đọc chắc chắn; `normalized_value=null`
  và note nêu nguyên nhân.
- `AMBIGUOUS`: có từ hai cách hiểu hợp lý; `normalized_value=null`, điền
  `candidate_values` và note.
- `UNKNOWN`: thiếu dữ liệu để phân biệt các trường hợp trên; các value là
  `null`, block để `[]`, bắt buộc có note.

Không dùng chuỗi `"null"`, `"N/A"`, `"không có"` thay cho JSON `null`.

## 4. So sánh A/B và adjudication

Chỉ sau khi **cả A và B đã hoàn thành độc lập**, chạy:

```powershell
.\.venv\Scripts\python.exe scripts\w3_gold_workflow.py compare R001
```

Lệnh sẽ kiểm tra schema, receipt/run linkage và block ID. Nếu A/B hợp lệ, nó
tạo:

- `data/kie_annotations/final/R001.json`;
- `data/kie_annotations/adjudication/R001.json` nếu có bất đồng.

Field A/B đồng ý được chuyển nguyên sang final. Field bất đồng vẫn để trống;
adjudicator phải xem ảnh, điền quyết định cuối, `decision_reason`,
`rule_reference`, ID và thời gian. Không ưu tiên A, không chọn ngẫu nhiên và
không dùng KIE prediction để xử lý bất đồng.

## 5. Chuẩn bị và QA Oracle OCR

Oracle draft ban đầu chỉ là bản sao có kiểm soát từ Real OCR với
`ocr_run_id` riêng. Người chuẩn bị phải đối chiếu ảnh và:

- sửa `text` sai;
- bổ sung block OCR bỏ sót khi có polygon xác định được;
- tách/gộp block nếu cần nhưng giữ `block_id` duy nhất;
- đặt `reading_order` liên tục từ `0`;
- giữ polygon bốn điểm chuẩn hóa `[0,1]` theo TL, TR, BR, BL;
- không đổi `receipt_id` hoặc kích thước ảnh;
- đổi engine thành provenance phù hợp sau khi hoàn tất draft;
- không coi confidence là xác suất. Chỉ dùng `1.0` cho evidence do người thật
  kiểm tra theo protocol của nhóm và phải mô tả rõ trong provenance;
- đặt `average_confidence` bằng trung bình confidence của mọi block, làm tròn
  6 chữ số.

Ghi mọi khác biệt Real-vs-Oracle vào phiếu QA:

- `omissions`: Real OCR thiếu vùng chữ;
- `substitutions`: Real OCR nhận sai ký tự/nội dung;
- `other`: segmentation, thứ tự đọc hoặc geometry.

Sau khi Oracle đã chốt bytes, lấy hash:

```powershell
.\.venv\Scripts\python.exe scripts\w3_gold_workflow.py oracle-hash R001
```

Chép hash vào `oracle_sha256`, điền người chuẩn bị/thời gian, rồi chuyển file
cho **reviewer độc lập**. Chỉ reviewer mới điền `reviewer_id`, `reviewed_at`,
`independent_review_confirmed=true`, `qa_state="VERIFIED"` và provenance.
Nếu Oracle thay đổi sau review, hash cũ không còn hợp lệ và phải review lại.

## 6. Kiểm tra tiến độ và chạy evaluation

Xem riêng một receipt:

```powershell
.\.venv\Scripts\python.exe scripts\w3_gold_workflow.py status --test-id R001
```

Kiểm tra nghiêm ngặt toàn bộ 40 receipt:

```powershell
.\.venv\Scripts\python.exe scripts\w3_gold_workflow.py validate
```

Sau khi tất cả A/B/final/adjudication/Oracle QA đều hợp lệ, KIE owner chạy
lệnh sau với provenance thật của đợt annotation:

```powershell
.\.venv\Scripts\python.exe scripts\w3_gold_workflow.py promote-manifest `
  --annotation-provenance "Mô tả batch, annotator, adjudicator và QA evidence"
```

Lệnh này chỉ promote khi các quyết định người thật đã tồn tại và pass gate; nó
không tự suy nhãn. Cuối cùng chạy:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_kie.py
```

Trước khi con người hoàn thành dữ liệu, trạng thái đúng phải là
`WAITING_FOR_VERIFIED_FIELD_ANNOTATIONS`, `evaluated=0`, `metrics=null`.
