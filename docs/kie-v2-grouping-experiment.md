# Issue #49: protocol và thí nghiệm grouping (đề xuất)

Liên quan [#49](https://github.com/vietreceipt-team/vietreceipt/issues/49),
[#59](https://github.com/vietreceipt-team/vietreceipt/issues/59), phụ thuộc dữ liệu
[#47](https://github.com/vietreceipt-team/vietreceipt/issues/47).
Ngày kiểm tra: 23/10/2026. **Chưa được TV1/TV2 duyệt protocol; chưa nghiệm thu accuracy.**

## Baseline và phạm vi thay đổi

- Baseline gốc: `07b2945ab191eb2db7658082f06e8550ac0f11b4`, working tree sạch trước sửa.
  [Bản ghi môi trường](experiments/kie49/baseline.json): Python 3.12.15,
  jsonschema 4.26.0; 96 KIE tests và shared contracts pass trước sửa.
- `geometry_grouping_v2`: extractor `deterministic-invoice-kie/2.0.4`,
  configuration `invoice-baseline/2.1.0`. Provider backend vẫn là
  `ai.kie.v2:extract_invoice`, chữ ký không đổi.
- `column_interval_grouping_v2_1`: extractor `deterministic-invoice-kie/2.2.0`,
  configuration `invoice-column-intervals/2.2.0`. Thử gán **block số nằm trọn
  trong đúng một khoảng header** cho quantity/unit_price/amount. Trường hợp còn
  lại dùng grouping cũ. Bản 2.2.0 thêm nhãn `Tên hàng / dịch vụ`, giữ dòng có
  description + ít nhất hai cột số khỏi bị nhầm thành footer/header, và dừng bảng
  hàng ở nhãn inline `Thuế suất GTGT:`. Các sửa này dựa trên train VRSYN2-00001.
  Không thay visual rows, continuation, normalization hoặc tax grouping. Không sửa text/sinh số.
- Variant dùng `extract_with_grouping(..., grouping=...)`, không có config global
  mutable hay monkeypatch lúc chạy A/B. Hai phương án nhận bản sao của cùng evidence
  đã kiểm hash, cùng gold, UUID, evaluator và matching. Gold không đi vào extractor.
- [Fingerprint baseline](../tests/fixtures/kie49/baseline-sha256.json) chụp **trước
  khi sửa runtime**, khóa toàn output của 12 ca, gồm review, raw, provenance và IDs.
  Đây là khóa hành vi, không phải gold độc lập để đánh giá accuracy. Test hồi quy
  dùng expected khai báo độc lập. Không coi 12 ca là chứng minh bất biến mọi input.

Containment vẫn là giả thuyết từ unit fixture. Các sửa nhãn/ranh giới bảng 2.2.0
xuất phát từ source và evidence TV2 train; giữ baseline mặc định đến khi có paired
benchmark được QA. ID grouping giữ nguyên, **config/extractor version đã tăng**;
không trộn kết quả variant 2.1.0 và 2.2.0. Xem [intake và gallery](kie49-tv2-intake.md).

## Metric đề xuất: `invoice-evaluation-2.2.0`

Matching giữ nguyên `source-overlap-cardinality-1.0`: cạnh tồn tại khi tập source
IDs của một dòng gold giao với source IDs của dòng prediction. Augmenting paths
tối đa **số cặp**, không tối đa tổng overlap. Ưu tiên overlap lớn rồi index prediction;
duyệt gold theo thứ tự file. Không dùng giá trị/status đang chấm, không dựa vào
gold `line_id`, không đưa expected IDs vào prediction. Split/merge chỉ được match
một-một. Khi nhiều dòng chia sẻ evidence, tie có thể phụ thuộc thứ tự; JSON xuất
từng cặp và `shared_gold_evidence_pairs` để người review thấy giới hạn này.

Gộp micro bằng tổng số đếm trên tài liệu, không trung bình score từng tài liệu.
Gọi M = matched rows, P = predicted rows, G = gold rows; N = số tài liệu.

| Metric/key | Công thức và mẫu số |
| --- | --- |
| `lines.detection_precision` | M/P |
| `lines.detection_recall` | M/G |
| `lines.detection_f1` | 2M/(P+G) |
| `lines.extra_row_rate` | (P−M)/P |
| `lines.matched_row_cell_correctness` | số ô đúng / số ô gold khác UNKNOWN trong các cặp |
| `lines.per_column_correctness[f]` | ô đúng của cột f / số ô gold khác UNKNOWN của cột f trong các cặp |
| `lines.complete_line_accuracy` | cặp có đủ **5 ô** đúng / số dòng gold có đủ 5 ô khác UNKNOWN |
| `headers[f].exact_match` | header đúng / số gold khác UNKNOWN của trường đó |
| `header_micro_accuracy` | tổng header đúng / tổng header gold khác UNKNOWN (micro, không phải macro) |
| `complete_header_accuracy` | tài liệu có đủ 13 header đúng / tài liệu có đủ 13 header gold khác UNKNOWN |
| `complete_table_accuracy` | tài liệu có số dòng bằng nhau và mọi dòng đúng / tài liệu có tất cả ô bảng gold khác UNKNOWN |
| `complete_invoice_accuracy` | tài liệu đúng header **và line_items** / tài liệu có tất cả ô header+bảng gold khác UNKNOWN |

“Đúng” = exact tuple `(status, normalized_value)`. Không fuzzy-match, không bỏ ô
khó hoặc chỉ chấm ô PRESENT. Gold UNKNOWN bị mask khỏi giá trị/presence/strict
completion; các status còn lại vẫn được chấm, phải khớp cả status và null. Report
xuất `header_coverage`, `per_column_scored`, `matched_cells_unknown` và các count
`scoreable_*`. Row detection vẫn dùng mọi dòng gold kể cả dòng chứa UNKNOWN. Kiểu số canonical theo contract: VND nguyên,
USD tối đa 2 chữ số thập phân; không ép chuỗi thành số để chấm. Header precision,
recall và F1 hiện có lấy TP là PRESENT đúng value; PRESENT sai value vừa là FP
vừa là FN. Các count và mẫu số được xuất cùng score.

**Mọi mẫu số 0 → null.** P=G=0: row F1/recall/precision/cell/complete-line null,
nhưng bảng rỗng đúng bảng gold rỗng nên complete-table=1 cho tài liệu đó.
P>0,G=0: F1=0, precision=0, extra rate=1, recall/complete-line=null.
P=0,G>0: F1=0, recall=0, precision/extra/cell=null, complete-line=0.
N=0: accuracy tài liệu/header null. Điểm cell trên matched rows luôn phải đọc cùng
G/P/M và F1; shared evidence có thể cho F1=1 dù nội dung sai hoàn toàn.

`UNKNOWN` = chưa xác định; `NOT_PRESENT` = có cơ sở xác nhận không có/không áp dụng;
`UNREADABLE` = nguồn có nhưng không đọc được; `AMBIGUOUS` = không phân giải được.
Bốn trạng thái khác nhau dù đều normalized=null. Không có cột unit → NOT_PRESENT;
có cột nhưng không có block ô → UNKNOWN. OCR bỏ mất nội dung **không** biến source
gold thành NOT_PRESENT. Ô gold UNKNOWN không được chấm; dòng có UNKNOWN không vào mẫu số strict
complete-line/table/invoice. Đó là thay đổi version 2.2.0 theo dự thảo TV1 PR #64,
chưa phải đồng ký protocol. Không tái sử dụng điểm từ evaluator cũ.

**Tax breakdown chưa được chấm**: annotation v2 không có `tax_breakdown`.
`tax_amount` trong 13 header có được chấm; đó không phải accuracy từng nhóm thuế.
JSON gắn scope rõ ràng. Multi-VAT có regression test giữ hành vi và provenance,
nhưng muốn full invoice bao gồm thuế cần TV1/TV2 chốt gold schema + matching riêng.
Không được gọi metric hiện tại là full business invoice hoặc end-to-end accuracy.

## Gate dữ liệu và mẫu số failure

Đã nhận PR #66: 80 candidate từ 20 base documents (train 60/validation 20), source
gold và output Reader thật; **0 bản reviewed**, chưa có aligned gold đủ điều kiện.
`data/invoice_v2/manifest.json` vẫn không có. Manifest V1 và unit fixtures không thay thế gold.
Không mở final test/gold final để tìm lỗi; không sửa nhãn, không tự cấp VERIFIED.

Manifest vẫn phải frozen, VERIFIED có reviewer/thời điểm có timezone, đủ sample
count, đúng configuration, provenance và hash của từng artifact. Gold phải đủ
13 header/5 ô mỗi dòng, đúng identity/split/types và mọi source ID phải thuộc
Reader evidence; PRESENT phải có evidence, mỗi dòng phải có ít nhất một source ID.
Không align được do OCR omission: fail eligibility, bàn giao source gold và lỗi
cho TV2/TV3, không xóa dòng hoặc giả block ID.

Tất cả records được preflight; báo từng record lỗi, sample ID nếu đọc được, artifact,
stage và lý do. Có lỗi → không chạy extraction. Nếu extraction của bất kỳ phương
án/mode nào lỗi → không xuất score cho subset; giữ raw prediction đã chạy để debug,
toàn bộ metrics/modes/variants/delta vẫn null và `evaluated=0`. `coverage` chứa
required/manifest_records/eligible/processed/evaluated/fraction. `processed` là
số tài liệu mọi phương án/mode yêu cầu đã chạy xong, không phải số được chấm.
Nếu manifest thiếu, required và fraction=null (không đoán corpus có 0 mẫu).

Đây là module KIE có **aligned evidence**, không tự đo lỗi source→Reader. Pipeline
end-to-end TV5 phải giữ tổng nguồn ban đầu và mọi routing/OCR failure. Đã thêm
`ai/kie/v2/source_evaluation.py`: kernel match bằng vùng nguồn theo trang, không
dùng gold OCR IDs; input lỗi dùng `result=None` và vẫn tính sai mọi ô/dòng đã biết,
strict completion=0 kể cả bảng rỗng. Kernel không cấp quyền chạy final: caller phải
QA gold/regions, xác minh source identity/hash và mapping tọa độ. Xem hợp đồng
trong [intake](kie49-tv2-intake.md). Không ghép mẫu số kernel vào report KIE-aligned.
Nếu sau này cho phép subset, cần một run riêng công khai danh sách loại/mẫu số gốc;
runner này không có tùy chọn bỏ qua gate.

## Chạy và tái lập

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-contracts.txt
.venv/bin/python -m unittest tests.test_kie_baseline tests.test_kie_evaluation \
  tests.test_kie_artifacts tests.test_kie_v2 tests.test_kie_v2_evaluation \
  tests.test_kie_v2_grouping tests.test_kie_v2_source_evaluation tests.test_kie_v2_handoff -v
.venv/bin/python tests/contracts/run_contract_tests.py

# Thiếu manifest: exit 2, WAITING_FOR_VERIFIED_V2_GOLD, metrics=null.
.venv/bin/python scripts/evaluate_invoice_kie.py --compare --output results/kie49-waiting

# Chỉ chạy khi TV2 bàn giao manifest phát triển/validation đã QA phù hợp.
.venv/bin/python scripts/evaluate_invoice_kie.py --manifest /path/to/dev/manifest.json \
  --compare --output results/kie49-ab-001
```

Thư mục output phải mới. `report.json` lưu metadata, hash manifest/code, commit/
dirty flag, version extractor/config/evaluator/matching, sample counts, slices
theo `input_type`/`template_id`/`error_group`, gold, prediction và từng cặp dòng.
`summary.csv`: baseline/variant/delta và mẫu số; `samples.csv`: từng mẫu/mode/variant;
`failures.csv`: lỗi record hoặc cả run. File thiếu metadata slice vào UNSPECIFIED;
slice rất ít mẫu chỉ có tính mô tả, không chứng minh tổng quát hóa. `error_group`
là metadata đầu vào, không phải nguyên nhân đã được công cụ xác nhận.

Manifest single-config cũ chỉ cho chạy đúng config đó. A/B cần giữ
`configuration={"name":"invoice-baseline","version":"2.1.0"}` và **khai báo mới
do người sở hữu manifest review/freeze**, không chỉ sửa QA flag cho chạy được:

```json
"experiment": {
  "protocol": "grouping-ab-1.0",
  "evaluator_version": "invoice-evaluation-2.2.0",
  "configurations": {
    "geometry_grouping_v2": {"name":"invoice-baseline","version":"2.1.0"},
    "column_interval_grouping_v2_1": {"name":"invoice-column-intervals","version":"2.2.0"}
  }
}
```

`--compare` chỉ cho split `train`/`validation` (từ “development” map thành train
theo annotation schema). Split test/benchmark bị từ chối **trước đọc artifacts**.
Chạy riêng bằng `--grouping <tên>` vẫn phải có manifest cho đúng config; không tự
thêm quyền A/B. Split/template/parent leakage cần báo cáo QA TV2, runner không
thể chứng minh disjointness từ một manifest chỉ có một split.

## Ablation và cảnh báo

Grouping A/B giữ nguyên normalization/checks. Không có ablation “tắt chuẩn hóa”
trong production. Chỉ bật diagnostic trước/sau khi manifest khai báo
`raw_value_protocol="selected-value-text-v1"` được QA cùng gold: `raw_value` của
PRESENT phải là **chuỗi giá trị được in**, bỏ nhãn trường, giữ format lựa chọn
(kể cả newline khi ghép fragment), không phải `str(normalized_value)`.

Khi đó JSON từng mẫu/mode xuất số đúng predicted→raw và normalized→canonical,
cùng denominator = PRESENT headers + PRESENT cells **trong matched rows**.
Prediction thiếu tính sai. Không so `raw_text` (có thể chứa nhãn/nhiều block) trực
tiếp với số canonical. Cohort này không bao gồm dòng bỏ sót, phải đọc cùng F1;
không coi chênh lệch EM giữa hai representation là causal gain của normalization.
Không khai báo raw protocol → `NOT_RUN_QA_RAW_GOLD_REQUIRED`, metrics=null.

Consistency chỉ xuất PASS/WARNING/SKIPPED và số warning riêng; test đảm bảo không
đổi predicted/normalized/status. Warning không chứng minh giá trị đã được sửa đúng.
Oracle tùy chọn vẫn cần QA, giữ receipt/run, IDs, reading order, geometry,
confidence và engine; chỉ thay text. Gap chỉ xuất khi toàn tập paired, mode_counts
cho biết coverage oracle. Oracle không thể khôi phục block/geometry đã bị OCR mất.
Taxonomy tự động là **dấu hiệu**, không là nguyên nhân được xác minh.

## Kết quả hiện tại và failure gallery

| Phép đo | Số mẫu đủ điều kiện | Baseline | Variant | Delta |
| --- | --- | --- | --- | --- |
| TV2 development/validation: row F1, cell, complete-line, 13 fields | 0/80 candidate (20 hóa đơn gốc) | null | null | null |

Trạng thái: **WAITING_FOR_VERIFIED_V2_GOLD**. Chưa có paired benchmark; chưa đủ
căn cứ kết luận variant tốt hơn. [Bàn giao và PR draft](kie49-handoff.md).

Các quan sát dưới đây là **software diagnostics tổng hợp**, không phải tập TV2,
không có QA benchmark và không đưa vào bảng accuracy trên:

[Failure example JSON](experiments/kie49/synthetic-column-diagnostic.json) lưu
toàn evidence, expected row độc lập, output hai phương án, status/raw/provenance,
metric tính từ matching và content hash cho ca số căn phải.

| Sample / nguồn | Gold/expected độc lập; output baseline → variant | Phân tích |
| --- | --- | --- |
| `narrow-right-aligned`, [fixture](../tests/kie_v2_grouping_fixtures.py) | Một dòng Service A/box/2/50000/100000; q UNKNOWN + price AMBIGUOUS → đủ 5 ô đúng. M=P=G=1, F1 1→1; cell 3/5→5/5; complete-line 0→1 | Gán cột: block `p0_b8` (2, x=.52–.54) gần mép trái header giá hơn header lượng; containment chọn đúng cột. Cơ chế xác nhận trên fixture, chưa phải prevalence thực tế. |
| `wrapped-description` | Dịch vụ mẫu + continued name → cùng một description ở cả hai; raw newline và ID `wrapped` giữ nguyên, review AMBIGUOUS_FORMAT | Giữ hành vi nối dòng và sự không chắc chắn; không chứng minh phân biệt được sản phẩm mới ở gần. |
| `close-partial-item`, [regression test](../tests/test_kie_v2_grouping.py) | Expected hai sản phẩm A/B, khi B nằm gần A thì cả hai phương án vẫn trả một dòng A B có AMBIGUOUS_FORMAT | Giới hạn grouping còn nguyên; giữ cả evidence và cảnh báo, không nhận là đã sửa. |
| `split-description` | Dịch vụ + mẫu → Dịch vụ mẫu ở cả hai; ID `split` còn trong evidence | Ghép fragment tên cùng hàng vẫn được hỗ trợ. |
| `merged-numeric-block` | Source in 50000 và 100000; Reader giả gộp thành `50000 100000` → unit_price không phân giải, amount UNKNOWN ở cả hai | Segmentation/column limitation; không cắt chuỗi đoán tiền. Không có bằng chứng OCR model gây lỗi vì đây là fixture. |
| `missing-unit-column` / `missing-unit-cell` | unit NOT_PRESENT / UNKNOWN giữ nguyên hai phương án | Tách thiếu cột với ô bị mất; source thật cần TV2 xác minh. |
| `unheaded` | Source có Product/2/100 nhưng hai phương án không nhận bảng | Unsupported layout; chưa có giải pháp có bằng chứng. |
| `multiple-vat` | 5%/100000/5000 và 8%/200000/16000 giữ nguyên | Regression thuế; không phải tax accuracy benchmark. |
| `generated-text-pdf`, [Reader test](../tests/test_kie_v2_reader.py) | Hai dòng Service A continued và Service B, đủ 5 ô; cả hai đạt 2/2 complete lines | PDF tổng hợp → **Reader/PDFium thật**. Alignment test từ literal in trên PDF, tạo trước khi chạy KIE; không giả output Reader. Không có OCR ảnh trong test. |

Các loại lỗi cần gắn nhãn khi có dữ liệu: OCR omission/substitution;
geometry/reading order; candidate/role selection; row grouping/column alignment;
normalization/currency/VAT; gold/alignment; unsupported layout. Với mỗi ví dụ mới
ghi sample ID, source/evidence hash + IDs, source gold, aligned gold, output hai
phương án, tác động metric và cột `confirmed`/`hypothesis`. Ngoài những cơ chế
fixture nêu trên, chưa có nguyên nhân trên dữ liệu thực được xác minh.

Reader smoke tái lập (không cần model OCR):

```bash
.venv/bin/python -m pip install Pillow==10.4.0 numpy==1.26.4 pypdfium2==5.12.1 reportlab==4.4.10
.venv/bin/python -m unittest tests.test_kie_v2_reader -v
```

[Bản ghi PDF smoke](experiments/kie49/reader-smoke.json) ghi hash source/evidence/
output đã chạy local, và [báo cáo availability](experiments/kie49/availability.json)
ghi null metrics đúng trạng thái thiếu dữ liệu. Full artifact local nằm trong
`results/kie49/reader-smoke/` (gitignored). Hàm `reader_case()` trong test tái tạo
PDF và trả `(pdf, evidence, audit, gold_test)` để lưu/kiểm lại; Reader duration
có thể khác giữa các lần chạy, nên hash evidence mới cần được ghi theo từng run.
Trong smoke này 12 header được kỳ vọng UNKNOWN và currency PRESENT; không phải
kiểm chứng trích đủ 13 giá trị trên source có đầy đủ thông tin.

Đã replay KIE trên saved Reader evidence thật cho cả PDF text/PNG/scan/blur từ
PR #66; không chạy lại PaddleOCR local, không đánh đồng với full pipeline. Bốn
evidence của một hóa đơn train được lưu làm regression cùng hash/provenance;
expected PDF text chép từ source preview, không lấy prediction làm gold benchmark. Backend/frontend schema và normalization rules
không đổi; default provider và thuế giữ nguyên.

Schema `experiment` có tại [invoice-kie-experiment.v1.schema.json](../schemas/invoice-kie-experiment.v1.schema.json).
Lấy đúng khai báo bằng `python scripts/evaluate_invoice_kie.py --print-experiment`;
lệnh chỉ in contract đề xuất, không tạo manifest VERIFIED hay approval.
Các JSON cũ trong `docs/experiments/kie49/` là snapshot lịch sử tại version ghi
trong từng file; bản ghi mới là `tv2-intake.json` và `verification-20261023.json`.
