# Table extraction — phân công Đồng và Tâm

Ngày lập: 03/11/2026. Liên quan [issue #49](https://github.com/vietreceipt-team/vietreceipt/issues/49).
Phân công theo yêu cầu của Đồng: Tâm nhận phần cấu trúc bảng/đánh giá ở
[issue #75](https://github.com/vietreceipt-team/vietreceipt/issues/75), Đồng nhận
adapter và tích hợp. GitHub assignee của Tâm là `phamduyductam-design`.
Việc phân công chưa có nghĩa Tâm đã xác nhận nhận việc hay
đã hoàn thành; trạng thái thực hiện theo dõi ở issue và PR của từng người.

## Mục tiêu và phạm vi PR đầu

Nhánh Table nhận vùng bảng từ nhóm Layout, dùng text **kèm vị trí** từ Reader,
trả các dòng hàng có cấu trúc và evidence để pipeline tổng hợp. Header/metadata,
footer và mô hình phân vùng toàn trang thuộc các phần việc khác.

Repo đã có baseline ở `ai/kie/v2/extraction.py` và biến thể thử nghiệm ở
`ai/kie/v2/grouping.py`. PR nền tảng tái sử dụng hai cách này qua module
`ai/table`, bổ sung giao diện nhận vùng bảng, ghép nhiều vùng vào kết quả hóa đơn
V2 và kiểm thử bàn giao. Chưa có mô hình Table được huấn luyện; worker mặc định
vẫn dùng baseline vì nhóm Layout chưa bàn giao provider/vùng dự đoán.
Không tuyên bố tăng accuracy từ các test tổng hợp.

## Chia công việc

| Người | Phần sở hữu | Đầu ra / nghiệm thu |
| --- | --- | --- |
| Đồng | Giao diện Table, evidence, adapter nhận vùng từ Layout, ghép nhiều vùng/trang vào hóa đơn V2 | `ai/table/extractor.py`, `ai/table/pipeline.py`, test Table/pipeline/Reader; ID dòng duy nhất, kiểm tra tổng tiền toàn hóa đơn, validation và tài liệu |
| Tâm | Thuật toán cấu trúc bảng: hàng/cột, mô tả nhiều dòng, OCR tách/gộp ô, ô gộp, bảng có viền/không viền/chỉ ngang/chỉ dọc | Issue #75, PR riêng cho thuật toán/fixtures; dữ liệu development có nhãn; so sánh baseline/variant cùng tập và error analysis |
| Cả hai | Chốt giao diện với nhóm Layout/Reader; review chéo; đánh giá rồi mới chọn cách tích hợp | Ví dụ input/output thống nhất; log/test; cấu hình được khóa trước final test |

Để giảm sửa cùng file: Đồng giữ adapter/pipeline và test bàn giao; Tâm bắt đầu bằng
module `ai/table/structure.py`, fixtures và `tests/test_kie_table_structure.py`
trong PR kế tiếp. Đây là vị trí dự kiến, chưa có implementation trong PR đầu.
Tâm thêm strategy có tên/phiên bản riêng sau khi hai người thống nhất giao diện;
không đổi âm thầm baseline đang dùng trong worker. Đồng ghép strategy vào adapter
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

## Phần tích hợp của Đồng — đã thực hiện

```python
from ai.table import extract_invoice_with_tables

result = extract_invoice_with_tables(
    evidence,
    kie_run_id=kie_run_id,  # uuid.UUID do caller cấp
    regions=[
        {"page_index": 0, "bbox": [0.0, 0.33, 1.0, 0.65]},
        # Các vùng còn lại do Layout cung cấp, không hard-code cho hóa đơn thật.
    ],
)
```

- Hàm ghép hóa đơn nhận danh sách vùng, sắp xếp theo trang/top/left, cấp `line_id`
  duy nhất trên toàn hóa đơn. Từ chối vùng giao nhau/cùng vùng trên cùng trang.
- Dùng header/footer/tax extraction hiện có, loại evidence trong vùng Table khỏi
  header candidates, lấy currency từ metadata rồi mới chuẩn hóa các ô tiền.
- Sau khi ghép đủ dòng mới chạy consistency checks và validation schema/evidence
  toàn kết quả. Không dùng lại warning từ lần kiểm tổng trên tập dòng khác.
- Danh sách vùng thiếu/rỗng, vùng sai/giao biên hoặc **bất kỳ vùng nào không phát
  hiện dòng** đều gây lỗi. Không trả hóa đơn thiếu một bảng như một kết quả thành công.
  Hàm `extract_table` cấp thấp vẫn trả `NO_ROWS_DETECTED` để chẩn đoán từng vùng.
- Kết quả ghép có extractor `layout-region-invoice-kie` và configuration riêng cho
  grouping, không gắn metadata baseline lên một pipeline đã nhận vùng Layout.
- Caller phải lưu manifest vùng Layout (và version/hash model tương ứng) cùng
  evidence gốc/run metadata để tái lập. Schema invoice giữ nguyên; bbox không được
  nhét thêm vào root invoice trái hợp đồng.
- Kiểm thử pipeline nhiều vùng/trang, input lỗi, tránh trùng dòng và checks sau
  ghép nằm ở `tests/test_kie_table_pipeline.py`. Reader test chạy cả adapter vùng
  và hàm ghép hóa đơn trên output PDFium thật từ PDF tổng hợp.

Phụ thuộc tiếp theo: nhóm Layout bàn giao provider và ví dụ vùng dự đoán với
Reader cho PDF text/scan; sau review mới nối vào worker. Phần wiring đến provider
Layout chưa tồn tại không được đánh dấu đã chạy end-to-end. Strategy cấu trúc mới
của Tâm sẽ ghép sau PR thực hiện issue #75, giữ baseline và chạy lại kiểm thử hợp đồng.

## Bàn giao thuật toán / đánh giá — Tâm phụ trách (issue #75)

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
/tmp/vietreceipt-table-venv/bin/python -m unittest tests.test_kie_table tests.test_kie_table_pipeline tests.test_kie_v2 tests.test_kie_v2_grouping -v
/tmp/vietreceipt-table-venv/bin/python tests/contracts/run_contract_tests.py
git diff --check
```

Kiểm chứng cập nhật ngày 03/11/2026: Python 3.12 chạy **157 test** thuộc các suite
KIE baseline/evaluation/artifacts/V2/Table/pipeline/grouping/source/handoff/Reader;
shared contracts, Ruff và `pip check` đạt. Trong đó có 10 test adapter, 7 test
pipeline và 2 test Reader (gồm hàm ghép hóa đơn trên PDF tổng hợp qua PDFium thật,
cả hai grouping). Cài dependency Reader theo `.github/workflows/kie-tests.yml`
để chạy Reader tests. Hai evaluator vẫn exit 2, metrics/modes null khi chưa đủ gold.

Fixture là dữ liệu tổng hợp kiểm thử phần mềm; kết quả này không thay thế benchmark
trên hóa đơn thật, source gold đã QA hoặc đánh giá cuối sau freeze.
