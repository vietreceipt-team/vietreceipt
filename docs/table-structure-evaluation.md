# Báo cáo cấu trúc bảng — Tâm / issue #75

Ngày 03/11/2026. Liên quan [#75](https://github.com/vietreceipt-team/vietreceipt/issues/75),
[#49](https://github.com/vietreceipt-team/vietreceipt/issues/49) và adapter của Đồng
trong [PR #76](https://github.com/vietreceipt-team/vietreceipt/pull/76).

**Trạng thái benchmark: `NOT_SCORED`, `metrics=null`.** Đã có thuật toán opt-in,
regression tests, ảnh nguồn tổng hợp và phép chạy development có thể tái lập.
Chưa có gold Table do TV2/reviewer độc lập QA hoặc protocol được đồng ký để
công bố accuracy. Không kết luận strategy tốt hơn trên hóa đơn thật, không đóng #75/#49.

## Đã hoàn thành

- Thêm `ai/table/structure.py`, strategy `conservative_intervals_v1`, configuration
  `conservative-intervals/1.0.0`; baseline `geometry_grouping_v2` dùng đúng
  `invoice-baseline/2.1.0` và implementation cũ để đối chiếu.
- Dùng khoảng giữa các header làm ranh giới cột; nối fragment lệch theo chiều dọc
  khi không xung đột cột. Ghép mô tả nhiều dòng nhưng giữ cờ `AMBIGUOUS_FORMAT`.
- Ô số bị OCR tách thành nhiều block hoặc gộp qua nhiều cột giữ nguyên block/text,
  trả `AMBIGUOUS`, không suy diễn số. Ô gộp dọc được gắn lại các dòng bị ảnh hưởng,
  giữ source ID chung và yêu cầu review; không nhân bản thành giá trị chắc chắn.
- Phân biệt không có cột đơn vị (`NOT_PRESENT`) với ô đơn vị trống (`UNKNOWN`).
  Giữ từng bảng/header lặp và từng trang riêng; line ID được cấp theo thứ tự kết quả.
- Thêm 16 ca development tổng hợp, 15 test chuyên biệt, bốn ảnh PNG nguồn với
  evidence/expected/provenance/hash; thêm test đi qua Reader PDFium thật trên
  PDF tổng hợp có đủ bốn kiểu đường viền.
- Thêm runner paired `scripts/evaluate_table_structure.py`, JSON aggregate/per-sample,
  thời gian, failure/no-row counts, config, source và implementation SHA-256.
  Tái sử dụng trực tiếp `ai/kie/v2/evaluation.py:metrics`; không sửa matching/UNKNOWN.
- Thêm đường chạy vào CI, kể cả chạy lại test Reader sau khi cài dependency tùy chọn.
  `.gitattributes` cố định LF cho artifact kiểm hash và source mới. Bốn fixture Reader
  cũ không đổi Git blob; sửa checkout CRLF về LF đã khôi phục hash gốc trên Windows.
- Đọc adapter/pipeline của Đồng ở commit `ad442a809e1b276417e8b7b24529f480059763eb`,
  chạy kiểm thử tương thích trong bản sao riêng: **34/34 test đạt**.
  Chi tiết và điều kiện ghép ở [báo cáo review](table-adapter-review.md).

Không đổi schema, normalization, evaluator, header/footer extraction hoặc mặc định
worker. Không dùng pretrained model, thêm weights hay dữ liệu riêng tư.

## Giao diện bàn giao đề xuất

```python
from ai.table.structure import extract_table_structure, structure_rows

table = extract_table_structure(
    evidence,                    # Reader 1.3 hoặc document-2.0, evidence nguyên bản
    page_index=0,
    bbox=(0.0, 0.18, 1.0, 0.60), # chỉ là vùng fixture; Layout cung cấp vùng thật
    currency="VND",              # caller lấy từ metadata, không tự mặc định
    strategy="conservative_intervals_v1",
)
rows = table["line_items"]

# Callback đề xuất cho adapter sau khi Đồng review/chấp thuận:
# rows = structure_rows(selected_blocks, currency=currency, strategy=strategy)
```

`selected_blocks` là các `Block` đã validate, chọn trong vùng tọa độ trang gốc;
không phải crop-local. API vùng kiểm evidence toàn tài liệu, page/bbox và từ chối
block cắt biên; không tạo block ID hoặc sửa text/polygon/confidence/reading order.
Ô và dòng có evidence/status/review metadata V2. Kết quả vùng là intermediate,
không tự nhận là toàn bộ `InvoiceKIEResultV2`.

`NO_ROWS_DETECTED` luôn cần review; block không thuộc bảng nhận diện được nằm trong
`unassigned_block_ids`. Có dòng cũng không chứng minh mọi block trong vùng đã được
giải quyết. Pipeline phải lưu thất bại/vùng chưa giải quyết, cấp line ID duy nhất
sau ghép và chạy consistency/validation cuối cùng.

Đây là giao diện **đề xuất**, chưa phải xác nhận của Đồng. Chưa nối strategy mới
vào `ai.table.extract_table`, invoice provider hoặc worker. Không truyền tên strategy
mới vào `grouping` của PR #76 vì nhánh đó hiện chỉ chấp nhận hai grouping cũ.

## Dữ liệu, provenance và split

Nguồn: `tests/fixtures/table_structure/provenance.json` và
`tests/kie_table_structure_fixtures.py`. 16 ca tương ứng 13 base document tổng hợp,
**một template**, tất cả thuộc development. Bốn biến thể `bordered`, `borderless`,
`horizontal`, `vertical` cùng `ruling-base-1`, cùng split và cùng evidence tọa độ.
Không cộng bốn ảnh như bốn template độc lập. Các ca còn lại kiểm mô tả nối/tách,
quantity lệch, số tách/gộp, thiếu đơn vị, partial item, header lặp, nhiều trang,
không header và vùng trống. Ô gộp dọc có thêm regression riêng trong test suite.

PNG được vẽ từ scene literal bằng Pillow 11.3.0; manifest ghi generator/version/hash,
kích thước gốc, hệ tọa độ, checksum PNG/evidence/expected, license và trạng thái
`NOT_INDEPENDENTLY_REVIEWED`. Evidence ảnh là scene tổng hợp, **không phải OCR đã chạy**.
Expected values/IDs được khai báo từ scene trước khi gọi hai strategy, không lấy từ
prediction. Runner kiểm checksum và đối chiếu scene lưu trên đĩa trước khi đo.

Strategy chỉ nhận text + geometry, không đọc pixel đường kẻ. Bốn PNG chứng minh có
nguồn hình ảnh tái lập; test PDFium kiểm đường Reader text thật. Chúng chưa chứng minh
khả năng nhận đường kẻ từ ảnh, OCR scan hoặc tổng quát hóa sang template khác.

### Gói cần TV2/reviewer bàn giao tiếp

Chưa gửi yêu cầu hay xác nhận thay TV2. Checklist cụ thể để phối hợp:

1. Nguồn development cho bốn kiểu viền, gồm cả PDF text và scan/ảnh; ghi license,
   source hash, `template_id`, `base_document_id`; mọi biến thể cùng base phải cùng split.
2. Gold source độc lập cho hàng/ô, đơn vị thiếu, ô gộp và các status; reviewer thật
   ghi người duyệt/thời điểm/hash. Tách source gold khỏi alignment theo OCR block ID.
3. Vùng bảng trên trang gốc đã review, Reader evidence/config/version/hash, mapping
   source→evidence; giữ cả trường hợp Layout/Reader thất bại trong cohort.
4. Đồng/TV1/TV2 xác nhận giao diện, matching/UNKNOWN và mẫu số trước scored A/B.
   Khóa strategy/config trước final; không đọc final test để chọn ngưỡng.

## Lệnh tái lập và kiểm chứng

Từ root repo, dùng Python trong virtualenv. Dependencies contract theo
`requirements-contracts.txt`; Reader test cần thêm Pillow, numpy, reportlab 4.4.10
và pypdfium2 5.12.1 như workflow. Để tái tạo đúng PNG đã lưu, dùng Pillow 11.3.0.

```powershell
python -m venv .venv-table
.venv-table/Scripts/python.exe -m pip install -r requirements-contracts.txt
.venv-table/Scripts/python.exe -m pip install Pillow==11.3.0 numpy==2.3.2 reportlab==4.4.10 pypdfium2==5.12.1 ruff==0.14.3
.venv-table/Scripts/python.exe scripts/generate_table_structure_sources.py
.venv-table/Scripts/python.exe -m unittest discover -s tests -p 'test_kie*.py' -q
.venv-table/Scripts/python.exe tests/contracts/run_contract_tests.py
.venv-table/Scripts/ruff.exe check ai/table/structure.py scripts/evaluate_table_structure.py scripts/generate_table_structure_sources.py tests/kie_table_structure_fixtures.py tests/test_kie_table_structure.py
.venv-table/Scripts/ruff.exe format --check ai/table/structure.py scripts/evaluate_table_structure.py scripts/generate_table_structure_sources.py tests/kie_table_structure_fixtures.py tests/test_kie_table_structure.py
.venv-table/Scripts/python.exe scripts/evaluate_table_structure.py --output /tmp/table-not-scored.json
# Exit 2 có chủ đích: NOT_SCORED, metrics=null, synthetic_diagnostics=null.
.venv-table/Scripts/python.exe scripts/evaluate_table_structure.py --synthetic-diagnostics --repeats 5 --output /tmp/table-diagnostic.json
# Vẫn exit 2; số chẩn đoán tổng hợp chỉ nằm trong synthetic_diagnostics.
git diff --check
```

Trên Windows có thể thay `/tmp/...` bằng một đường dẫn ghi được. Linux dùng
`.venv-table/bin/python` thay đường dẫn Scripts. Snapshot kiểm chứng local chạy
Windows 11/Python **3.13.7**, numpy 2.3.2, Pillow 11.3.0, jsonschema 4.26.0,
reportlab 4.4.10, pypdfium2 5.12.1; CI vẫn dùng Python 3.12/dependency của workflow.

Kết quả local: **154/154 KIE tests đạt**, gồm 15 test Table structure; shared
contracts đạt; Ruff/check format và whitespace đạt. Test Reader mới thực thi đủ
bốn kiểu viền bằng PDFium, không skip trong lần chạy local này. CI remote cần
được đọc riêng, không suy từ kết quả local.

## Kết quả paired development — chỉ chẩn đoán phần mềm

Snapshot [comparison.json](experiments/table75/comparison.json) chạy trên implementation
commit `37c944595886590dd67c025253db692715c9b3c6`. Mỗi file implementation có hash
canonical LF trong report; từng mẫu có hash evidence/expected và vùng được cấp.
[not-scored.json](experiments/table75/not-scored.json) ghi đường chạy mặc định không
công bố số accuracy. Cả hai có `status=NOT_SCORED`, `metrics=null` ở cấp chính thức.

| Chỉ số tổng hợp | Baseline | conservative_intervals_v1 |
| --- | ---: | ---: |
| Gold rows G | 27 | 27 |
| Predicted rows P | 26 | 25 |
| Matched rows M | 25 | 25 |
| Row precision M/P | 25/26 = 0.9615 | 25/25 = 1.0000 |
| Row recall M/G | 25/27 = 0.9259 | 25/27 = 0.9259 |
| Row F1 2M/(P+G) | 50/53 = 0.9434 | 50/52 = 0.9615 |
| Matched known cells correct | 119/124 = 0.9597 | 120/124 = 0.9677 |
| Complete known line | 20/25 = 0.8000 | 21/25 = 0.8400 |
| Complete known table | 10/14 = 0.7143 | 11/14 = 0.7857 |
| Exception failure count | 0/16 | 0/16 |
| Có vùng không ra dòng (gồm negative empty) | 2/16 | 2/16 |
| Median thời gian mỗi lần gọi API vùng | 3.837 ms | 3.762 ms |

Matching hiện có `source-overlap-cardinality-1.0`, one-to-one theo source ID,
không theo giá trị. Cell correctness chấm status + normalized value bằng kernel cũ.
`UNKNOWN` bị loại khỏi cell denominator; status khác vẫn được chấm. 25 matched
rows có 125 ô, một ô UNKNOWN nên 124 ô được chấm. Complete-line loại hai gold row
có UNKNOWN, còn 25/27; complete-table loại hai sample có UNKNOWN, còn 14/16.
Negative `empty` có bảng gold rỗng và vẫn thuộc denominator strict của kernel;
điều đó không cấp quyền coi vùng trống là thành công trong pipeline.
Mẫu số bằng 0 trả null. Header/tax/complete-invoice không thuộc phép đo này.

Per-column correct/known: description 24/25 ở cả hai; unit 24/24 ở cả hai;
quantity 24/25 → 25/25; unit_price 23/25 ở cả hai; amount 24/25 ở cả hai.
Failure giữ `None` trong kernel, không bỏ mẫu khỏi gold/table denominator; test
inject failure cho 16/16 input xác nhận điều này. No-row không phải exception,
nên cần đọc cả row misses lẫn failure count, không chỉ cột failure.

Timing gồm validation evidence + chọn vùng + cấu trúc bảng; không gồm Layout/OCR,
upload, rendering hoặc network. Chạy tuần tự, đổi thứ tự hai strategy theo sample,
5 lần/sample, không warmup. Số median khác nhỏ không đủ chứng minh nhanh hơn;
re-run có thể khác timing nhưng cấu trúc output/hash phải giữ nguyên.

## Đúng, sai và phân loại lỗi

- `staggered-quantity`: baseline tách quantity thành dòng thừa; strategy mới gắn
  lại đúng source row. Đây là cải thiện chẩn đoán Table trên một scene tổng hợp.
- `wrapped-description`: giữ đủ text/IDs và cờ review. `ambiguous-partial-next-item`
  vẫn có thể ghép nhầm một mặt hàng thiếu số vào mô tả trước; không coi đã sửa.
- `split-number` và `merged-numbers`: chưa khôi phục giá trị đúng. Strategy giữ
  raw text/source, trả AMBIGUOUS thay vì ghép token hoặc tách số phỏng đoán.
- `unheaded`: không ra dòng; cần header nhận diện được. Trang tiếp nối không có
  header hoặc một ô thực sự kéo qua hai trang cũng chưa được nối tự động.
- Vùng Layout sai/cắt block: lỗi **Layout/boundary**; API từ chối và caller phải
  lưu failure. Fixture vùng đúng không chứng minh Layout dự đoán đúng.
- Reader bỏ/sai text, gộp/tách OCR không đúng source: lỗi **OCR/Reader**. Table
  chỉ bảo toàn evidence và nêu bất định, không nhận là sửa được OCR.
- Evidence đúng và vùng đúng nhưng nhóm hàng/cột sai: lỗi **Table**. Chỉ so sánh
  lỗi Layout dự đoán với vùng nguồn đã QA sau khi được bàn giao cả hai bộ vùng.

## Còn lại trước nghiệm thu toàn bộ issue

- TV2/reviewer QA dữ liệu development, đủ kiểu viền và template/base split.
- Đồng xác nhận callback/metadata, review strategy và nối dispatch trong PR tích hợp
  riêng; chạy lại checks toàn invoice. Review local ở đây không thay chấp thuận của Đồng.
- TV1/TV2/Đồng chốt protocol rồi chạy scored A/B hợp lệ; hiện chỉ có diagnostics.
- Chạy dữ liệu ảnh/scan thật và vùng Layout dự đoán; chưa chứng minh end-to-end.
- Reviewer kiểm PR và CI remote đạt trước merge. Chưa tự merge hoặc đổi default worker.
