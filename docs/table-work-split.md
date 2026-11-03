# Table extraction — phân công anh và Tâm

Ngày lập: 03/11/2026. Liên quan [issue #49](https://github.com/vietreceipt-team/vietreceipt/issues/49).
Đây là **đề xuất phân công**, chưa phải xác nhận nhận việc hay nghiệm thu của Tâm.

## Mục tiêu và phạm vi PR đầu

Nhánh Table nhận vùng bảng từ nhóm Layout, dùng text **kèm vị trí** từ Reader,
trả các dòng hàng có cấu trúc và evidence để pipeline tổng hợp. Header/metadata,
footer và mô hình phân vùng toàn trang thuộc các phần việc khác.

Repo đã có baseline ở `ai/kie/v2/extraction.py` và biến thể thử nghiệm ở
`ai/kie/v2/grouping.py`. PR nền tảng tái sử dụng hai cách này qua module
`ai/table`, bổ sung giao diện nhận vùng bảng và kiểm thử bàn giao. Đây chưa phải
mô hình table extraction được huấn luyện, cũng chưa phải tích hợp Layout vào
worker sản xuất. Không tuyên bố tăng accuracy từ các test tổng hợp.

## Chia công việc

| Người | Phần sở hữu | Đầu ra / nghiệm thu |
| --- | --- | --- |
| Anh | Giao diện Table, evidence, adapter nhận vùng từ Layout, tích hợp output với pipeline | `ai/table/extractor.py`, `tests/test_kie_table.py`, tài liệu này; test vùng/trang/ID/tọa độ và tương thích dòng hàng V2 |
| Tâm (đề xuất) | Thuật toán cấu trúc bảng: hàng/cột, mô tả nhiều dòng, OCR tách/gộp ô, ô gộp, bảng có viền/không viền/chỉ ngang/chỉ dọc | PR riêng cho thuật toán và fixtures; dữ liệu development có nhãn cấu trúc; so sánh baseline/variant cùng tập và error analysis |
| Cả hai | Chốt giao diện với nhóm Layout/Reader; review chéo; đánh giá rồi mới chọn cách tích hợp | Ví dụ input/output thống nhất; log/test; cấu hình được khóa trước final test |

Để giảm sửa cùng file: anh giữ adapter và test bàn giao; Tâm có thể bắt đầu bằng
module `ai/table/structure.py`, fixtures và `tests/test_kie_table_structure.py`
trong PR kế tiếp. Đây là vị trí dự kiến, chưa có implementation trong PR đầu.
Tâm thêm strategy có tên/phiên bản riêng sau khi hai người thống nhất giao diện;
không đổi âm thầm baseline đang dùng trong worker. Anh ghép strategy vào adapter
sau review và chạy lại kiểm thử hợp đồng.

## Giao diện đang chạy được

```python
from ai.table import extract_table

table = extract_table(
    evidence,                    # OCRResult 1.3 hoặc document-2.0 nguyên bản
    page_index=0,                # zero-based
    bbox=(0.0, 0.33, 1.0, 0.65), # left, top, right, bottom; normalized trang gốc
    currency="VND",              # từ metadata đã trích xuất, không mặc định đoán VND
)
rows = table["line_items"]
```

- Layout phải bàn giao page index và bounding box **trên trang gốc**, gồm cả
  tiêu đề cột. Ví dụ bbox trên chỉ phù hợp fixture `tests.kie_v2_fixtures.invoice`;
  không được hard-code cho hóa đơn thật.
- Adapter nhận evidence nguyên bản. Không nhận ảnh crop hoặc tự chạy OCR; text,
  confidence, polygon và reading order được giữ trong evidence gốc, tra lại qua
  `source_block_ids` và `source_ocr_run_id`. Không tạo artifact OCR mới hoặc đổi ID.
- Nếu OCR chỉ chạy trên crop, nhóm Reader phải có adapter đổi tọa độ/ID về evidence
  chuẩn trước khi gọi hàm này. Giao diện crop-local chưa được hỗ trợ.
- Chỉ chọn block nằm trọn trong vùng và đúng trang. Block giao biên có diện tích
  dương gây `ValueError`; cần nhóm Layout/Reader rà lại vùng hoặc việc tách block.
  Không âm thầm bỏ một phần block. Block chỉ chạm biên không được xem là giao nhau.
- Bbox sai, không hữu hạn, ngoài [0, 1], page không tồn tại, evidence không hợp lệ
  hoặc grouping không được hỗ trợ sẽ gây lỗi. Pipeline tương lai phải lưu stage
  failure, không coi lỗi là bảng rỗng thành công.
- Output có `adapter_version`, identity nguồn, page/bbox, extractor/configuration,
  các ID block trong vùng và `line_items`. Đây là **kết quả trung gian**, chưa phải
  toàn bộ `InvoiceKIEResultV2`.
- Mỗi dòng có `line_id`, description/unit/quantity/unit_price/amount, evidence và
  review metadata V2. `source_block_ids` ở cấp kết quả gồm cả header trong vùng;
  ID cấp dòng/ô chỉ gồm evidence của dòng/ô đó. Status `EXTRACTED` chỉ nghĩa là có
  dòng được phát hiện, không phải xác nhận dòng đúng hay đã được người dùng duyệt.
- Không ra dòng thì `status=NO_ROWS_DETECTED`; không được suy ra hóa đơn không có
  hàng hóa. Bảng không có header nhận diện được hiện vẫn chưa xử lý được.
- Currency thiếu giữ bất định tiền tệ; currency chưa hỗ trợ giữ review reason.
  Không suy diễn số tiền từ phép nhân, subtotal hoặc tổng thanh toán.
- `grouping` mặc định là `geometry_grouping_v2`; thử nghiệm hiện có phải chọn rõ
  `column_interval_grouping_v2_1`. Metadata output ghi đúng phiên bản đã dùng.

## Bàn giao tích hợp tiếp theo — phần của anh

1. Chốt ví dụ Layout/Reader thực tế cùng nhóm phụ trách; kiểm cả PDF text và scan.
2. Gọi Table adapter cho từng vùng, giữ thứ tự trang/vùng. Các kết quả hiện đánh
   `line_id` riêng từ `line-0001`; khi ghép nhiều vùng phải cấp lại ID duy nhất trên
   toàn hóa đơn, giữ nguyên source IDs và kiểm tra vùng trùng để không nhân đôi dòng.
3. Ghép với header/footer, gọi consistency checks **sau** khi đủ dòng và số tổng,
   rồi validate toàn bộ kết quả bằng `ai.kie.v2.contract.validate_result` với
   evidence và KIE run ID gốc. Adapter riêng không chạy checks liên vùng/toàn hóa đơn.
4. Thêm test worker/pipeline và ghi rõ extractor/configuration cho strategy được
   chọn trước khi chuyển cấu hình production.

## Bàn giao thuật toán / đánh giá — phần đề xuất cho Tâm

- Lập các ca development: bốn kiểu đường viền, tên nhiều dòng, cột lệch, thiếu ĐVT,
  OCR tách/gộp ô, bảng nhiều trang và tiêu đề lặp. Không đánh dấu đã hỗ trợ chỉ vì
  text fixture chạy qua; baseline này chưa sử dụng pixel đường kẻ bảng.
- Phối hợp TV2 lấy dữ liệu/nhãn đã QA; chia theo template/base document, giữ mọi
  biến thể cùng split. Bắt đầu trên development, không mở final test để chọn model.
- Nếu thử model có sẵn: ghi nguồn/license, phiên bản/checksum weights, cấu hình,
  tài nguyên và lệnh chạy; so sánh với baseline trước khi đề nghị đưa dependency vào.
- Dùng evaluator hiện có (`ai/kie/v2/evaluation.py`, `source_evaluation.py`), không
  tự đổi matching hoặc UNKNOWN policy. Báo row precision/recall/F1, cell correctness,
  complete-line/table, thời gian và số mẫu lỗi; ghi rõ scope/mẫu số và provenance.
- So sánh nhận vùng đúng với nhận vùng dự đoán để phân biệt lỗi Layout, OCR và Table.
  Chỉ báo accuracy khi gold/protocol đủ điều kiện; không gán điểm cho dữ liệu chưa QA.

## Chạy lại kiểm thử PR nền tảng

```bash
python3.12 -m venv /tmp/vietreceipt-table-venv
/tmp/vietreceipt-table-venv/bin/python -m pip install -r requirements-contracts.txt
/tmp/vietreceipt-table-venv/bin/python -m unittest tests.test_kie_table tests.test_kie_v2 tests.test_kie_v2_grouping -v
/tmp/vietreceipt-table-venv/bin/python tests/contracts/run_contract_tests.py
git diff --check
```

Kiểm chứng bổ sung của PR ngày 03/11/2026: Python 3.12 chạy **148 test** thuộc
các suite KIE baseline/evaluation/artifacts/V2/Table/grouping/source/handoff;
shared contracts đạt; Ruff và `pip check` đạt. Cài thêm dependency theo bước Reader
trong `.github/workflows/kie-tests.yml` rồi chạy `tests.test_kie_v2_reader`:
**2 test đạt**, gồm adapter trên vùng bảng của PDF tổng hợp qua PDFium thật, với
cả hai grouping. Hai evaluator vẫn trả exit 2 và metrics null khi chưa đủ gold.

Fixture là dữ liệu tổng hợp kiểm thử phần mềm; kết quả này không thay thế benchmark
trên hóa đơn thật, source gold đã QA hoặc đánh giá cuối sau freeze.
