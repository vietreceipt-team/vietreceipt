# VietReceipt KIE Semantic Gold Protocol

- Status: Frozen for W2 annotation
- Version: 0.1
- Split: `kie-evaluation-split-v0.1`
- Scope: Five canonical KIE fields

## 1. Purpose

Tài liệu này quy định cách tạo semantic ground truth cho KIE.

Các file `data/ground_truth/R001.txt` đến `R040.txt` là ground truth
transcription phục vụ OCR, không phải semantic gold cho KIE.

KIE semantic gold chỉ gồm đúng năm field:

1. `merchant_name`
2. `receipt_date`
3. `total_amount`
4. `invoice_id`
5. `merchant_address`

## 2. Frozen evaluation split

Canonical split:

`ai/kie/resources/kie-evaluation-split-v0.1.csv`

Split gồm:

- 20 `development`
- 20 `held_out`

Development samples được phép dùng để debug và chỉnh rule của baseline.

Held-out semantic labels không được dùng để chỉnh candidate rules,
ranking weights, normalization rules hoặc review thresholds của baseline v0.1.

Không thay đổi membership của frozen split sau khi xem kết quả evaluation.

## 3. Independent double annotation

Mỗi receipt dùng trong official KIE evaluation phải được hai người khác nhau
gán nhãn semantic độc lập.

Ví dụ:

```text
R001
├── annotation A
└── annotation B
````

Annotator B không được xem annotation A trước khi hoàn thành annotation của mình.

Cả hai annotator:

* dùng cùng source receipt image;
* dùng cùng `source_ocr_run_id`;
* dùng cùng field specification;
* dùng cùng annotation guideline version;
* không xem KIE prediction khi tạo ground truth;
* không dùng Internet hoặc nguồn ngoài ảnh để suy diễn giá trị.

Mỗi annotation là một record riêng theo:

`schemas/annotation-record.schema.json`

## 4. Agreement

Hai annotation được coi là đồng ý với nhau khi quyết định semantic giống nhau.

Cần so sánh:

* `annotation_status`;
* `normalized_value`;
* `candidate_values` nếu status là `AMBIGUOUS`;
* source evidence nếu khác biệt evidence làm thay đổi ý nghĩa field.

Khác biệt nhỏ trong cách viết `annotator_note` không tự động được coi là
semantic disagreement.

## 5. Adjudication

Nếu hai annotator không đồng ý về một field, không được:

* chọn ngẫu nhiên;
* ưu tiên annotator A;
* lấy majority vote;
* dùng KIE prediction làm đáp án.

Trường hợp disagreement phải được adjudicate.

Adjudicator xem:

* source image;
* annotation A;
* annotation B;
* field specification;
* annotation guidelines.

Adjudication phải lưu:

* labels ban đầu;
* final decision;
* lý do;
* adjudicator identity;
* thời gian quyết định.

Hai annotation ban đầu không được ghi đè hoặc xóa.

## 6. Final gold

Với mỗi field:

```text
nếu A và B đồng ý:
    final gold = agreed label
nếu A và B không đồng ý:
    final gold = adjudicated label
```

Một receipt chỉ được coi là `gold-ready` khi cả năm field đều có final label.

Chỉ final gold được dùng để tính official KIE evaluation metrics.

## 7. Status vocabulary

Gold annotation chỉ dùng:

* `PRESENT`
* `NOT_PRESENT`
* `UNREADABLE`
* `AMBIGUOUS`
* `UNKNOWN`

Không được dùng `NOT_PRESENT` chỉ vì OCR không tìm thấy field.

Non-`PRESENT` phải có:

`normalized_value = null`

## 8. OCR evidence

`source_block_ids` chỉ được tham chiếu các OCR block thuộc đúng
`source_ocr_run_id`.

Nếu field nhìn thấy rõ trên ảnh nhưng OCR bỏ sót, áp dụng rule
`OCR_OMISSION` của annotation contract.

Ground truth phải phản ánh nội dung trên receipt image, không được thay đổi
để khớp với OCR output.

## 9. Oracle vs Real OCR

Cùng một semantic gold sẽ được dùng cho hai chế độ evaluation:

* Real OCR: KIE nhận OCRResult thật.
* Oracle OCR: KIE nhận OCR evidence được kiểm soát từ ground truth.

So sánh hai chế độ giúp phân biệt:

* lỗi do OCR;
* lỗi do chính KIE.

## 10. Gold-ready checklist

Một receipt được đưa vào official KIE evaluation khi:

* [ ] thuộc frozen split;
* [ ] có source image xác định;
* [ ] có `source_ocr_run_id`;
* [ ] có annotation A;
* [ ] có annotation B;
* [ ] A và B là hai người khác nhau;
* [ ] annotation được thực hiện độc lập;
* [ ] mọi disagreement đã adjudicate;
* [ ] cả năm field có final gold;
* [ ] provenance/version metadata đầy đủ.
