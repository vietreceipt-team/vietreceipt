# Footer Extractor V1

Module trích xuất `subtotal`, `tax_amount` và `total_amount` từ một vùng Footer.
Layout hoặc người kiểm thử cung cấp vùng. OCR hoặc Document Reader cung cấp chữ
và tọa độ. Module ghép nhãn với số tiền bằng nội dung và vị trí trên trang.

## Giao diện

```python
from ai.kie.v2.footer import extract_footer

region = {"page": 0, "bbox": [0.05, 0.65, 0.95, 0.95]}
fields = extract_footer(evidence, region)
amounts = {field: cell["normalized_value"] for field, cell in fields.items()}
```

- `evidence` là kết quả OCR một trang hoặc envelope `document-2.0` của
  Document Reader. Mỗi block mang ID, text, polygon và reading order theo hợp
  đồng KIE V2.
- `page` là chỉ số trang bắt đầu từ 0. `bbox` là
  `[left, top, right, bottom]` trong hệ tọa độ chuẩn hóa của trang gốc.
  Gốc ở góc trên bên trái. Chọn vùng chứa trọn các block cần đọc. Một vùng
  không hợp lệ hoặc cắt ngang block trên trang được chọn sẽ gây `ValueError`.
- Module độc lập mặc định dùng `currency="VND"` cho hóa đơn Việt Nam. Khi
  tích hợp, truyền tiền tệ chuẩn hóa đã xác định cho hóa đơn, hoặc
  `currency=None` nếu chưa xác định. KIE V2 xử lý việc chuẩn hóa theo tiền tệ.
- `fields` chứa đủ ba field cell theo schema KIE V2. Mỗi cell giữ
  `normalized_value`, `value_status`, thông tin review và
  `source_block_ids` theo thứ tự đọc của nguồn. `raw_text` giữ nguyên chữ
  của các block nguồn. Số tiền VND hợp lệ được trả về dưới dạng số nguyên.

Ví dụ với các số tiền in trên hóa đơn là `100.000`, `8.000` và `108.000đ`,
`amounts` nhận giá trị sau.

```json
{"subtotal": 100000, "tax_amount": 8000, "total_amount": 108000}
```

## Quy tắc ghép

1. Lọc block theo trang và vùng. Nhận diện nhãn ở đầu block bằng các mẫu của
   KIE V2 và biến thể Footer như “Tổng tiền hàng” hoặc “VAT”. So khớp nhãn
   hỗ trợ chữ có hoặc không có dấu.
2. Đọc số ngay sau nhãn nếu chúng nằm trong cùng block. Với nhãn đứng riêng,
   tìm block giống số tiền ở bên phải, có phần chồng dọc tối thiểu 35% chiều
   cao của block thấp hơn. Nhãn mới hoặc một block chữ xen giữa giới hạn
   phạm vi ghép. Tỷ lệ VAT có thể đứng cạnh nhãn và được bỏ qua khi lấy số
   tiền thuế.
3. Dùng bộ chuẩn hóa và chọn ứng viên KIE V2. Nhiều giá trị khác nhau với
   điểm gần nhau tạo cell `AMBIGUOUS`. Một nhãn chưa ghép được số tiền tạo
   cell `UNKNOWN` và giữ lại block nhãn để đối chiếu. Dấu `?` hoặc ký tự
   thay thế Unicode trong ứng viên số tiền tạo cell `UNREADABLE`.
4. Khi có đủ ba số tiền VND, kiểm tra `subtotal + tax_amount = total_amount`
   với dung sai 1 VND. Sai lệch lớn hơn gắn `CONSISTENCY_WARNING` cho cả ba
   cell và giữ nguyên số đọc được.

## Chạy kiểm thử

Từ thư mục gốc VietReceipt với Python 3.12, chạy các lệnh sau.

```sh
python3.12 -m pip install -r requirements-contracts.txt
python3.12 -m unittest tests.test_footer_extractor -v
```

Sáu test dùng dữ liệu tổng hợp để kiểm tra ghép cùng hàng, số nằm chung
block với nhãn, lọc vùng và trang, ứng viên xung đột, trạng thái thiếu hoặc
không đọc được, và khả năng đưa các cell vào kết quả Invoice KIE V2.

## Phạm vi V1

V1 xử lý một vùng Footer trên một trang. Thuật toán tập trung vào nhãn và
số tiền trong cùng block hoặc cùng hàng. Ghép khác dòng, gộp nhiều mức thuế,
xử lý giảm giá và phân cột phức tạp là các trường hợp dành cho phiên bản sau.
Kết quả test tổng hợp xác nhận hành vi phần mềm. Đánh giá độ chính xác cần
tập hóa đơn Việt Nam có nhãn chuẩn và vùng Footer tương ứng.

Khi Layout bàn giao vùng Footer, caller có thể dùng ba cell trả về trong
`fields` của hóa đơn, rồi chạy kiểm tra toàn hóa đơn với line items và
`validate_result`. Giao diện độc lập hiện tại dùng được cả khi khoanh vùng
thủ công.
