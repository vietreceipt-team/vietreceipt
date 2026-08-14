# VietReceipt KIE Field Specification

- **Status:** Conditionally approved for implementation
- **Document version:** 1.1
- **Target shared contract:** Shared Integration Contracts v1.3; Backend JSON Schema/OpenAPI sync pending
- **Owner:** Dao Minh Phuong
- **Module:** KIE & Data Engineering
- **Related issue:** #1

## 1. Purpose and scope

Tài liệu này định nghĩa ý nghĩa, phạm vi và biểu diễn dữ liệu của năm trường KIE cốt lõi trong VietReceipt: tên cửa hàng, ngày giao dịch, tổng tiền, mã hóa đơn và địa chỉ cửa hàng. KIE nhận đầu vào là các OCR block có định danh, nội dung văn bản, tọa độ và độ tin cậy; sau đó lựa chọn hoặc ghép các block liên quan để tạo giá trị dự đoán cho từng trường.

Tài liệu là contract dùng chung giữa OCR, KIE, Backend và Frontend. OCR phải giữ nguyên các block nguồn; KIE phải trả lại giá trị dự đoán, giá trị chuẩn hóa và tham chiếu tới block nguồn; Backend phải bảo toàn các lớp dữ liệu và lịch sử chỉnh sửa; Frontend phải hiển thị được kết quả dự đoán để người dùng kiểm tra và sửa.

Phạm vi tuần 1 chỉ bao gồm định nghĩa dữ liệu và quy tắc diễn giải. Tài liệu này chưa khẳng định extractor đã hoàn chỉnh, chưa quy định ngưỡng confidence cuối cùng và chưa cung cấp kết quả Precision, Recall, F1 hay Exact Match.

Phê duyệt có điều kiện nghĩa là semantics trong tài liệu này đã được KIE Owner khóa để triển khai, nhưng các ràng buộc giao thoa với OCR và Backend vẫn phải được phản ánh trong shared JSON Schema/OpenAPI và được các owner tương ứng sign-off trước khi freeze contract chung.

## 2. Shared terminology and value layers

### 2.1 OCR raw data (`OCRResult` and OCR blocks)

- **Định nghĩa:** Kết quả nguyên bản do module OCR tạo ra. Mỗi OCR run có `ocr_run_id`; mỗi vùng chữ có tối thiểu `block_id`, `text`, `polygon`, `confidence` và `reading_order`.
- **Nguồn tạo:** Module OCR.
- **Quy tắc bất biến:** Không được sửa hoặc ghi đè sau khi đã lưu. Nếu chạy OCR lại, hệ thống phải tạo OCR run/version mới.
- **Vai trò trong KIE:** Là bằng chứng nguồn để KIE chọn candidate và để giao diện liên kết field với vùng chữ trên ảnh.
- **Geometry:** Mỗi `polygon` có đúng bốn điểm theo thứ tự top-left, top-right, bottom-right, bottom-left. Mỗi điểm có `x` và `y` là số trong `[0,1]`, gốc ở góc trên-trái, tính trên ảnh sau khi áp dụng EXIF orientation. Polygon không bắt buộc song song với cạnh ảnh.
- **Reading order:** `reading_order` là JSON integer duy nhất trong một OCR run, bắt đầu từ `0`, do OCR xác định và không bị KIE đánh số lại. Thứ tự này phải ổn định sau khi OCR run được lưu.
- **Owner boundary:** Đây là quyết định được KIE Owner chấp nhận làm input contract. OCR Owner vẫn phải xác nhận khả năng sản xuất đúng representation này và shared OCR schema phải enforce các ràng buộc tương ứng.

Ví dụ geometry minh họa:

```json
{
  "polygon": [
    {"x": 0.12, "y": 0.08},
    {"x": 0.45, "y": 0.08},
    {"x": 0.45, "y": 0.13},
    {"x": 0.12, "y": 0.13}
  ],
  "reading_order": 0
}
```

### 2.2 Machine source text and predicted value (`raw_text`, `predicted_value`)

- **`raw_text`:** Nội dung `text` nguyên bản của toàn bộ `source_block_ids`, ghép theo `reading_order` bằng ký tự xuống dòng `\n`. KIE không sửa chính tả, khoảng trắng bên trong block hoặc normalize nội dung này. Khi `source_block_ids` rỗng, `raw_text` phải là JSON `null`, không dùng chuỗi rỗng.
- **`predicted_value`:** Chuỗi giá trị mà KIE lựa chọn hoặc ghép từ một hay nhiều OCR block cho một field, trước bước chuẩn hóa. Giá trị này có thể là một phần của `raw_text`, ví dụ bỏ nhãn `Tổng thanh toán` và chỉ giữ amount.
- **Nguồn tạo:** Module KIE.
- **Quy tắc bất biến:** `raw_text` và `predicted_value` không bị ghi đè bởi normalization hoặc chỉnh sửa của người dùng. Một lần chạy KIE mới phải được nhận diện bằng version/run riêng.
- **Yêu cầu truy vết:** Field `PRESENT` phải có ít nhất một `source_block_id`. Rule-based inference vẫn phải dẫn tới các OCR block đầu vào, đồng thời ghi tên và version của rule.

### 2.3 Normalized value (`normalized_value`)

- **Định nghĩa:** Giá trị dạng chuẩn do hệ thống suy ra một cách xác định từ `predicted_value`, ví dụ ngày theo ISO 8601 hoặc tổng tiền dưới dạng số nguyên VND.
- **Nguồn tạo:** Quy tắc normalization của KIE.
- **Quy tắc bất biến:** Không sửa `predicted_value`. Khi không thể chuẩn hóa chắc chắn, trường này phải là `null` và field phải được đánh dấu cần kiểm tra.
- **Yêu cầu truy vết:** Khi `normalized_value` khác `null`, phải xác định được `normalization.rule` và `normalization.version` đã sử dụng.

### 2.4 Corrected value (`corrected_value`)

- **Định nghĩa:** Giá trị do người dùng xác nhận hoặc sửa qua giao diện human-in-the-loop.
- **Nguồn tạo:** Người dùng đã được hệ thống xác định danh tính.
- **Quy tắc bất biến:** Không ghi đè OCR raw, predicted hoặc normalized value. Mỗi lần sửa phải tạo một correction-history record gồm giá trị cũ, giá trị mới, người sửa và thời điểm sửa.
- **Correction theo trạng thái:** Một correction có thể xác nhận `NOT_PRESENT`, `UNREADABLE`, `AMBIGUOUS` hoặc `UNKNOWN`; vì vậy `has_correction=true` không đồng nghĩa `corrected_value` khác `null`.
- **Giá trị hiệu lực:** Backend tính cả `effective_status` và `effective_value` theo công thức dưới đây. `effective_value` tuyệt đối không fallback sang `predicted_value` và không thay thế các lớp dữ liệu gốc.

```text
nếu has_correction = true:
    effective_status = corrected_status
    effective_value = corrected_value, nếu corrected_status = PRESENT
                      null,            nếu corrected_status != PRESENT

nếu has_correction = false:
    effective_status = value_status
    effective_value = normalized_value, nếu value_status = PRESENT
                      null,             nếu value_status != PRESENT
```

Ví dụ một human correction xác nhận field không có trên hóa đơn:

```json
{
  "has_correction": true,
  "corrected_status": "NOT_PRESENT",
  "corrected_value": null,
  "effective_status": "NOT_PRESENT",
  "effective_value": null,
  "effective_needs_review": false
}
```

### 2.5 Review flags

- `machine_needs_review`: cờ bất biến do KIE trả về cho KIE run tương ứng. Human correction không được ghi đè cờ này.
- `effective_needs_review`: cờ do Backend tính từ machine result, correction và verification; Frontend dùng cờ này để hiển thị cảnh báo hiện tại.
- Khi `machine_needs_review=true`, `review_reasons` phải có ít nhất một phần tử. Mỗi reason phải có `code` thuộc enum được duyệt; `message` là mô tả tùy chọn phục vụ debug/UI.
- Khi extractor được triển khai, quyết định review phải truy vết được qua `review_policy_version`. `confidence` không tự mang nghĩa accept/reject nếu thiếu field, extractor version và review policy tương ứng.
- Confidence thresholds chưa được hiệu chỉnh trên validation set của VietReceipt. Không hard-code `0.60` hoặc `0.85` như acceptance criteria và không trình bày chúng như kết quả thực nghiệm.

Review reason codes ban đầu:

| Code | Khi sử dụng |
|---|---|
| `NO_CANDIDATE` | Không tìm được candidate và chưa đủ bằng chứng kết luận `NOT_PRESENT` |
| `LOW_CONFIDENCE` | Extractor policy đánh dấu confidence chưa đạt yêu cầu đã được version hóa |
| `MULTIPLE_CANDIDATES` | Có từ hai candidate hợp lý trở lên |
| `AMBIGUOUS_FORMAT` | Một giá trị có nhiều cách diễn giải hợp lệ |
| `UNREADABLE_SOURCE` | Có bằng chứng field xuất hiện nhưng nguồn không đọc đủ |
| `UNSUPPORTED_CURRENCY` | Currency không phải VND hoặc không thể chuẩn hóa an toàn thành VND |
| `NEGATIVE_AMOUNT` | Candidate tổng tiền mang giá trị âm |
| `MISSING_DATE_COMPONENT` | Ngày thiếu ngày, tháng hoặc năm |
| `UNSUPPORTED_TWO_DIGIT_YEAR` | Năm chỉ có hai chữ số trong contract v1 |
| `SOURCE_ROLE_UNCLEAR` | Không xác định được vai trò nghiệp vụ của candidate/source |
| `NORMALIZATION_FAILED` | Có predicted value nhưng deterministic normalizer không tạo được giá trị chuẩn |

### 2.6 Ownership of data layers

| Layer/field | Owner tạo dữ liệu | Có được ghi đè dữ liệu nguồn không? |
|---|---|---|
| OCR block `text`, `polygon`, `confidence` | OCR | Không |
| `raw_text`, `predicted_value`, `normalized_value`, `value_status` | KIE | Không; re-run tạo `kie_run_id` mới |
| `machine_needs_review`, `review_reasons`, `source_block_ids` | KIE | Không |
| `corrected_value`, `corrected_status`, `has_correction` | Backend/Human | Không ghi đè OCR/KIE output |
| `effective_value`, `effective_status`, `effective_needs_review` | Backend | Dẫn xuất, không phải dữ liệu nguồn |
| Correction history | Backend | Append-only theo hành động người dùng |

## 3. Missing, unreadable and uncertain values

Mọi giá trị không tồn tại phải dùng JSON `null`. Không dùng chuỗi rỗng, `"N/A"`, `"không có"` hoặc giá trị tự suy đoán thay cho dữ liệu thật.

Các trạng thái dùng chung:

- `PRESENT`: Field xuất hiện và có thể đọc đủ để gán nhãn.
- `NOT_PRESENT`: Người gán nhãn đã kiểm tra hóa đơn và xác nhận field không xuất hiện.
- `UNREADABLE`: Có bằng chứng cho thấy field xuất hiện nhưng ảnh không đủ rõ để đọc đáng tin cậy.
- `AMBIGUOUS`: Có từ hai candidate hợp lý trở lên hoặc nội dung có thể được diễn giải theo nhiều cách.
- `UNKNOWN`: Hệ thống chưa tìm được candidate hoặc chưa có người xác nhận; không được tự coi là `NOT_PRESENT`.

KIE có thể dự đoán `NOT_PRESENT` hoặc `UNREADABLE`, nhưng các trạng thái do máy tạo vẫn phải có `machine_needs_review=true` và chờ người dùng xác nhận. Chỉ người gán nhãn hoặc reviewer mới tạo được quyết định human-resolved. Khi KIE không tìm thấy candidate và không có đủ bằng chứng để phân biệt vắng mặt với không phát hiện được, output mặc định phải là `UNKNOWN`, `predicted_value=null`, `normalized_value=null` và `machine_needs_review=true`.

Các invariant theo status:

| `value_status` | `predicted_value` | `normalized_value` | `source_block_ids` | Machine review |
|---|---|---|---|---|
| `PRESENT` | Khác `null` và không rỗng | Đúng canonical type | Ít nhất một block | Theo review policy |
| `NOT_PRESENT` | `null` | `null` | Có thể rỗng | Bắt buộc `true` cho quyết định do máy tạo |
| `UNREADABLE` | `null` hoặc phần đọc chắc chắn | `null` | Chứa block bằng chứng nếu OCR tạo được | Bắt buộc `true` |
| `AMBIGUOUS` | `null` hoặc candidate chưa phân giải | `null` | Chứa các block candidate nếu có | Bắt buộc `true` |
| `UNKNOWN` | `null` | `null` | Có thể rỗng | Bắt buộc `true` |

Các yêu cầu `source_block_ids` trong bảng này áp dụng cho machine KIE output. Ground-truth annotation vẫn có thể để mảng rỗng khi OCR bỏ sót hoàn toàn vùng chữ nhưng annotator đọc được trực tiếp từ ảnh; trường hợp đó phải ghi `OCR_OMISSION` trong annotation note.

## 4. Core field specifications

### 4.1 Merchant name (`merchant_name`)

#### Definition

Tên thương hiệu, cửa hàng hoặc đơn vị bán hàng được thể hiện trên hóa đơn và giúp người dùng nhận biết nơi phát sinh giao dịch.

#### Include

- Tên cửa hàng hoặc thương hiệu nằm ở phần header của hóa đơn.
- Tên chi nhánh nếu đây là tên nhận diện chính được in trên hóa đơn.
- Tên pháp nhân khi hóa đơn chỉ thể hiện tên pháp nhân và không có tên thương hiệu khác.

#### Exclude

- Tên khách hàng, thu ngân hoặc nhân viên bán hàng.
- Tên ngân hàng, cổng thanh toán hoặc đơn vị vận chuyển nếu họ không phải người bán.
- Slogan, nội dung khuyến mại, website, email, số điện thoại và mã số thuế.

#### Candidate selection

Ưu tiên tên nhận diện người bán nằm gần đầu hóa đơn và có vai trò như header. Nếu đồng thời có tên thương hiệu và tên pháp nhân, chọn tên thương hiệu hướng tới khách hàng; tên pháp nhân được giữ trong candidate metadata để truy vết/review. Nếu không có thương hiệu thì dùng tên pháp nhân. Chỉ gán `AMBIGUOUS` khi không xác định được candidate nào là người bán chính sau khi áp dụng thứ tự ưu tiên này. Không suy luận tên cửa hàng từ logo không có chữ hoặc từ kiến thức bên ngoài ảnh.

#### Normalization

- Chuẩn hóa Unicode về NFC.
- Loại khoảng trắng ở đầu/cuối và gộp khoảng trắng lặp.
- Giữ nguyên dấu tiếng Việt và nội dung chữ của tên riêng.
- Không tự mở rộng tên viết tắt, sửa chính tả hoặc ánh xạ sang tên doanh nghiệp khác trong phiên bản 0.1.

#### Missing and unreadable handling

- Không có tên người bán trên hóa đơn: `NOT_PRESENT`.
- Có vùng tên người bán nhưng không thể đọc: `UNREADABLE`.
- Có nhiều tên và không xác định được tên chính: `AMBIGUOUS`.

### 4.2 Receipt date (`receipt_date`)

#### Definition

Ngày mà giao dịch bán hàng hoặc thanh toán trên hóa đơn được thực hiện. Field cốt lõi chỉ lưu phần ngày; thời gian có thể được giữ trong metadata hoặc field mở rộng sau này.

#### Include

- Ngày bán, ngày giao dịch hoặc ngày thanh toán gắn với giao dịch trên hóa đơn.
- Phần ngày trong timestamp của giao dịch khi hóa đơn in cả ngày và giờ.

#### Exclude

- Ngày hết hạn thẻ, hạn đổi trả, ngày sinh hoặc ngày của chương trình thành viên.
- Ngày xuất hóa đơn điện tử nếu có bằng chứng rõ đây không phải ngày giao dịch cần số hóa.
- Dãy số giống ngày nhưng không có đủ ngữ cảnh để xác định.

#### Candidate selection

Ưu tiên candidate có keyword như `ngày bán`, `ngày giao dịch`, `thời gian` hoặc `date/time` và nằm gần thông tin hóa đơn. Nếu có nhiều ngày hợp lệ nhưng không xác định được ngày giao dịch chính, gán `AMBIGUOUS` thay vì chọn tùy ý.

#### Normalization

- Dạng chuẩn: `YYYY-MM-DD` theo ISO 8601.
- Chỉ tạo normalized value khi xác định chắc chắn được ngày, tháng và năm.
- Không tự suy ra năm bị thiếu. Năm hai chữ số không được chuyển bằng pivot year trong v1; giữ predicted value, đặt `normalized_value=null`, `value_status=AMBIGUOUS`, `machine_needs_review=true` và dùng reason `UNSUPPORTED_TWO_DIGIT_YEAR`.
- Chuỗi có nhãn giao dịch tiếng Việt như `ngày`, `ngày bán` hoặc `ngày giao dịch` được phép áp dụng deterministic rule `DD/MM/YYYY` trong v1. Rule và version phải được ghi trong normalization metadata.
- Nếu không có bằng chứng locale nhưng chính tính hợp lệ của calendar chỉ cho phép một thứ tự, chọn thứ tự hợp lệ duy nhất. Ví dụ `14/08/2020` chỉ có thể là ngày 14 tháng 8; `08/14/2020` chỉ có thể là ngày 14 tháng 8 theo thứ tự tháng/ngày.
- Nếu cả hai thứ tự ngày/tháng đều hợp lệ và không có nhãn/ngữ cảnh xác định locale, giữ predicted value nhưng đặt `normalized_value=null`, `value_status=AMBIGUOUS`, `machine_needs_review=true` và dùng reason `AMBIGUOUS_FORMAT`.

#### Missing and unreadable handling

- Không in ngày giao dịch: `NOT_PRESENT`.
- Vị trí ngày tồn tại nhưng một phần ký tự không đọc được: `UNREADABLE`.
- Có nhiều cách diễn giải hợp lệ: `AMBIGUOUS`.

### 4.3 Total amount (`total_amount`)

#### Definition

Số tiền cuối cùng khách hàng phải thanh toán cho giao dịch, sau các khoản giảm giá và điều chỉnh được thể hiện trên hóa đơn.

#### Include

- Giá trị gắn với các nhãn như `tổng thanh toán`, `tổng cộng`, `thành tiền`, `phải trả` hoặc cách diễn đạt tương đương khi ngữ cảnh cho thấy đây là số tiền cuối cùng.
- Currency nếu được in rõ bằng ký hiệu hoặc mã tiền tệ.

#### Exclude

- Tạm tính, tổng tiền hàng trước giảm giá, thuế riêng, phí riêng hoặc tiền giảm giá.
- Tiền khách đưa, tiền mặt nhận, tiền trả lại hoặc số dư.
- Tổng của một dòng sản phẩm riêng lẻ.

#### Candidate selection

Ưu tiên amount có keyword chỉ nghĩa số tiền cuối cùng và thường nằm gần cuối hóa đơn. Không chọn amount chỉ vì nó là số lớn nhất. Nếu có nhiều tổng tiền hợp lý mà không xác định được vai trò, gán `AMBIGUOUS`.

#### Normalization

- VietReceipt v1 chỉ hỗ trợ tổng tiền bằng VND.
- `normalized_value` là JSON integer không âm, đơn vị VND, không chứa ký hiệu tiền tệ hoặc dấu phân cách hàng nghìn; ví dụ `81302`.
- `currency` có giá trị cố định `VND` trong contract v1.3.
- Nếu hóa đơn có bằng chứng rõ cho thấy sử dụng currency khác, hoặc amount không thể chuẩn hóa an toàn thành VND, không được tự quy đổi; gán `AMBIGUOUS` hoặc `UNKNOWN`, đặt `normalized_value=null` và yêu cầu review.
- Giá trị âm không được tự chấp nhận là tổng thanh toán; phải chuyển sang review.

#### Missing and unreadable handling

- Hóa đơn không thể hiện tổng thanh toán: `NOT_PRESENT`.
- Nhìn thấy nhãn tổng nhưng amount không đọc được: `UNREADABLE`.
- Không phân biệt được total với subtotal, tiền khách đưa hoặc tiền trả lại: `AMBIGUOUS`.

### 4.4 Invoice ID (`invoice_id`)

#### Definition

Mã định danh của hóa đơn hoặc giao dịch do đơn vị bán hàng in trên chứng từ để tra cứu giao dịch.

#### Include

- Giá trị gắn với nhãn như `số hóa đơn`, `số HĐ`, `mã hóa đơn`, `receipt no`, `invoice no` hoặc nhãn tương đương.
- Mã giao dịch hoặc số tham chiếu chỉ khi hóa đơn không có invoice/receipt number và ngữ cảnh thể hiện đây là định danh chính cần tra cứu; trường hợp này phải ghi lại `id_type`.

#### Exclude

- Mã số thuế, mã sản phẩm, barcode sản phẩm và mã khách hàng.
- POS ID, terminal ID, batch number, authorization code hoặc số thẻ nếu không được xác nhận là mã hóa đơn.
- Số điện thoại, ngày giờ và amount.

#### Candidate selection

Thứ tự ưu tiên là invoice/receipt number, sau đó mới đến transaction/reference number làm phương án thay thế. Nếu có nhiều mã cùng mức ưu tiên, gán `AMBIGUOUS` và giữ toàn bộ candidate để review.

#### Normalization

- Chuẩn hóa Unicode, loại khoảng trắng ở đầu/cuối và gộp khoảng trắng lặp.
- Giữ số `0` ở đầu; không chuyển invoice ID sang kiểu số nguyên.
- Giữ chữ cái và các ký tự phân tách có ý nghĩa như `-` hoặc `/`.
- Có thể chuẩn hóa chữ Latin sang chữ hoa nếu quy tắc này được ghi nhận bằng normalization version; không tự xóa ký tự khi chưa có căn cứ.

#### Missing and unreadable handling

- Không có mã hóa đơn/giao dịch phù hợp: `NOT_PRESENT`.
- Có nhãn mã hóa đơn nhưng mã không đọc được đầy đủ: `UNREADABLE`.
- Có nhiều mã hợp lý và không chọn được mã chính: `AMBIGUOUS`.

### 4.5 Merchant address (`merchant_address`)

#### Definition

Địa chỉ địa điểm bán hàng hoặc chi nhánh phát hành hóa đơn được in trên chứng từ.

#### Include

- Số nhà, tên đường, phường/xã, quận/huyện, tỉnh/thành phố và thông tin tầng/tòa nhà nếu thuộc địa chỉ cửa hàng.
- Nhiều OCR block liên tiếp khi chúng cùng tạo thành một địa chỉ.

#### Exclude

- Địa chỉ khách hàng, địa chỉ giao hàng hoặc địa chỉ thanh toán của người mua.
- Địa chỉ ngân hàng, cổng thanh toán hoặc đơn vị khác không phải người bán.
- Số điện thoại, email, website và mã số thuế.

#### Candidate selection

Ưu tiên địa chỉ cửa hàng/chi nhánh nằm gần merchant name. Nếu hóa đơn thể hiện cả trụ sở và chi nhánh bán hàng, ưu tiên địa chỉ chi nhánh nơi phát sinh giao dịch. Nếu không xác định được vai trò của từng địa chỉ, gán `AMBIGUOUS`.

#### Normalization

- Chuẩn hóa Unicode về NFC.
- Loại khoảng trắng ở đầu/cuối và gộp khoảng trắng lặp.
- Ghép các dòng địa chỉ theo reading order bằng dấu phẩy và một khoảng trắng.
- Không tự mở rộng viết tắt hành chính, sửa tên riêng, bổ sung đơn vị hành chính hoặc geocode trong phiên bản 0.1.

#### Missing and unreadable handling

- Không in địa chỉ người bán: `NOT_PRESENT`.
- Có vùng địa chỉ nhưng không thể đọc đủ nội dung: `UNREADABLE`.
- Có nhiều địa chỉ và không xác định được địa chỉ bán hàng: `AMBIGUOUS`.

## 5. Minimum KIE output and traceability requirements

Một `KIEResult` phải có `schema_version`, `receipt_id`, `kie_run_id`, `source_ocr_run_id`, extractor name/version, `duration_ms` và đúng năm key canonical:

- `merchant_name`;
- `receipt_date`;
- `total_amount`;
- `invoice_id`;
- `merchant_address`.

Mỗi field prediction do KIE tạo phải có tối thiểu:

- `raw_text`;
- `predicted_value`;
- `normalized_value`;
- `value_status`;
- `confidence` trong `[0,1]` khi extractor được triển khai;
- `machine_needs_review`;
- `review_reasons`;
- `source_block_ids`.

Khi extractor được triển khai, mỗi field còn phải truy vết được:

- `normalization.rule` và `normalization.version` khi `normalized_value` khác `null`;
- `review_policy_version` dùng để tạo `machine_needs_review`;
- extractor/model version ở cấp KIE run.

KIE không trả `corrected_value`, `corrected_status`, `effective_value`, `effective_status` hoặc `effective_needs_review`. Các thuộc tính này thuộc Backend public API.

Trong tuần 1 không có extractor nên không được bịa confidence hoặc duration. Các giá trị xuất hiện trong example chỉ minh họa shape và phải được ghi rõ là illustrative. Khi triển khai extractor, confidence phải được tạo bởi một quy tắc/model có version và có thể kiểm thử.

Không được tạo field value không có nguồn OCR mà không đánh dấu rõ nguồn suy ra. Mọi rule-based inference phải có version và có thể kiểm thử. Field `PRESENT` bắt buộc có ít nhất một `source_block_id`, và tất cả block được tham chiếu phải thuộc đúng `source_ocr_run_id` của KIE run. Nếu `machine_needs_review=true`, `review_reasons` bắt buộc có ít nhất một reason code.

## 6. Illustrative examples

Các giá trị trong mục này chỉ minh họa định dạng dữ liệu, không phải kết quả đo hoặc dữ liệu lấy từ dataset.

| Field | Predicted value | Normalized value | Ghi chú |
|---|---|---|---|
| `merchant_name` | `CUA HANG ABC` | `CUA HANG ABC` | Không tự bổ sung dấu nếu OCR không nhận được |
| `receipt_date` | `14/08/2020` | `2020-08-14` | Chỉ chuẩn hóa khi thứ tự ngày/tháng được xác định |
| `total_amount` | `81.302 VND` | `81302` (JSON integer) | Currency cố định là `VND` trong v1 |
| `invoice_id` | `HD-000123` | `HD-000123` | Giữ số 0 ở đầu |
| `merchant_address` | `12 Duong A, Quan B` | `12 Duong A, Quan B` | Không tự thêm địa danh bị thiếu |

Ví dụ field output minh họa cho total:

```json
{
  "raw_text": "Tổng thanh toán\n81.302 VND",
  "predicted_value": "81.302 VND",
  "normalized_value": 81302,
  "value_status": "PRESENT",
  "confidence": 0.94,
  "machine_needs_review": false,
  "review_reasons": [],
  "review_policy_version": "kie-review-policy/1.0.0",
  "normalization": {
    "rule": "vnd_amount_parser",
    "version": "1.0.0"
  },
  "source_block_ids": ["block_03", "block_04"]
}
```

Ví dụ năm hai chữ số không được normalize trong v1:

```json
{
  "raw_text": "Ngày: 14/08/20",
  "predicted_value": "14/08/20",
  "normalized_value": null,
  "value_status": "AMBIGUOUS",
  "confidence": 0.72,
  "machine_needs_review": true,
  "review_reasons": [
    {
      "code": "UNSUPPORTED_TWO_DIGIT_YEAR",
      "message": "Contract v1 không suy luận năm hai chữ số"
    }
  ],
  "review_policy_version": "kie-review-policy/1.0.0",
  "source_block_ids": ["block_07"]
}
```

## 7. Decisions and owner actions

| Decision | Current position | Owner/action required |
|---|---|---|
| Canonical field names | Accepted: `merchant_name`, `receipt_date`, `total_amount`, `invoice_id`, `merchant_address` | Backend/OCR/Frontend must mirror these names and remove interface aliases |
| Value statuses | Accepted: `PRESENT`, `NOT_PRESENT`, `UNREADABLE`, `AMBIGUOUS`, `UNKNOWN` | Backend shared schema/API must mirror and enforce |
| Total canonical type | Accepted: non-negative JSON integer VND | Backend shared schema/API must mirror and enforce |
| Date canonical type | Accepted: ISO `YYYY-MM-DD` | Backend shared schema/API must mirror and enforce |
| Run preservation | Accepted: immutable `ocr_run_id`, `kie_run_id` and `source_ocr_run_id` | OCR/KIE/Backend must implement append-only runs |
| OCR polygon and coordinate convention | KIE Owner accepted: normalized four-point polygon ordered TL, TR, BR, BL after EXIF orientation | OCR Owner must confirm production and shared-schema enforcement |
| OCR reading order | KIE Owner accepted: unique zero-based integer within OCR run | OCR Owner must confirm production and shared-schema enforcement |
| Source IDs for `PRESENT` | Accepted: minimum one OCR block from `source_ocr_run_id` | KIE implementation and shared schema must enforce |
| Review reasons when machine review is true | Accepted: minimum one reason from the initial enum | KIE implementation and shared schema must enforce |
| Review policy traceability | Accepted: record `review_policy_version`; do not infer decisions from confidence alone | KIE implementation and shared schema must enforce |
| Two-digit year | Accepted for v1: do not infer; return `AMBIGUOUS`, normalized `null` and review reason | Add normalizer/contract tests before extractor release |
| Numeric date order | Accepted: Vietnamese transaction label permits `DD/MM/YYYY`; otherwise use the sole calendar-valid ordering or return `AMBIGUOUS` | Add versioned normalization rule and tests |
| Brand versus legal entity | Accepted: prefer customer-facing brand; fall back to legal entity only when no brand exists | Validate edge cases during annotation pilot |
| Correction projection | Accepted: non-`PRESENT` effective status always has `effective_value=null` | Backend Owner must mirror in OpenAPI and projection tests |
| Raw text construction | Accepted: join unmodified source block text by `reading_order` with `\n` | KIE implementation and tests must enforce |

### 7.1 Conditions for final approval

Tài liệu có thể chuyển từ `Conditionally approved` sang `Approved` khi hoàn thành tất cả điều kiện sau:

- Shared JSON Schema/OpenAPI phản ánh các quyết định ở bảng trên; không tạo KIE schema cạnh tranh trong `ai/kie/`.
- Contract test từ chối field `PRESENT` không có source block hoặc tham chiếu block ngoài `source_ocr_run_id`.
- Contract test từ chối `machine_needs_review=true` khi `review_reasons` rỗng.
- Có test cho ngày mơ hồ, nhãn giao dịch tiếng Việt, năm thiếu và năm hai chữ số.
- Có test correction với `corrected_status != PRESENT` và `effective_value=null`.
- OCR, KIE và Backend Owner sign-off các phần thuộc quyền sở hữu tương ứng.

## 8. Shared contract references

Sau khi Backend contract PR đồng bộ các quyết định v1.1 và được merge, machine-readable sources of truth là:

- `/schemas/kie-result.schema.json` cho KIE output;
- `/schemas/ocr-result.schema.json` cho OCR input;
- `/openapi/openapi.yaml` cho Backend public API;
- `/docs/integration-contracts.md` cho semantics giữa các module.

Không tạo một KIE schema thứ hai trong `ai/kie/` vì hai schema cạnh tranh sẽ dễ bị lệch. Nếu tài liệu này mâu thuẫn với shared JSON Schema/OpenAPI đã được tất cả owner sign-off, phải mở Issue và cập nhật contract qua PR thay vì tự sửa một phía.

Cho tới khi việc đồng bộ hoàn tất, tài liệu này là semantic decision record của KIE Owner nhưng không được dùng để tuyên bố shared Backend/OCR contract đã freeze.
