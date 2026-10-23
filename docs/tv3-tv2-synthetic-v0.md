# TV3 — tiếp nhận TV2 synthetic v0, 23/10/2026

Đầu vào lấy từ PR [#60](https://github.com/vietreceipt-team/vietreceipt/pull/60),
commit `5e5b871dd1c7413f2d74acc175aad0f0186486f7`. Phần mô tả PR còn nói SVG-only,
nhưng commit này có 270 biến thể được kê trong `rendered/manifest.csv`:
30 mẫu gốc × (4 PNG + 4 PDF image-only + 1 PDF vector).

Phần TV3 tiếp tục issue [#48](https://github.com/vietreceipt-team/vietreceipt/issues/48)
bằng Reader hiện có, không thay generator hoặc nhãn của TV2. Lần chạy này chọn
`VRSYN-002`, `VRSYN-005`, `VRSYN-008`: 27 tài liệu validation của `layout_b`,
gồm 3/2/1 dòng hàng. Không tải hoặc chạy các chứng từ/nhãn train/test. Chỉ đọc
metadata toàn manifest để kiểm tra split và duplicate. Ba mẫu gốc cùng một layout
không chứng minh khả năng tổng quát hóa, và các biến thể không phải mẫu độc lập.

## Tiếp nhận dữ liệu và transcript

`scripts/prepare_tv2_reader_manifest.py` chuyển manifest CSV đường dẫn tương đối
repo thành manifest JSON tương đối thư mục thí nghiệm; dùng `variant_id` duy nhất,
`input_type + degradation` làm slice (cột `quality` của TV2 vẫn ghi clean cả khi
ảnh mờ/nhiễu/nghiêng). Công cụ giữ receipt UUID của nhãn nguồn, xác minh SHA-256,
khóa train/test, và chép chứng từ cùng SVG/JSON nguồn vào gói độc lập.

PNG/PDF tải từ GitHub khớp hash manifest. Riêng SVG/JSON trong commit có LF,
nhưng hash nguồn của TV2 được tính với CRLF. Bản Git nguyên byte được giữ trong
`results/dev/tv2-reader-v0/git-source-text/`; bản checkout riêng chuyển LF → CRLF
khớp đúng hash đã khai báo. Không sửa nội dung nhãn hoặc bỏ qua checksum.
[Bảng hash trước/sau](../results/dev/tv2-reader-v0/source-transfer-20261023.json)
ghi rõ phép chuyển xuống dòng. Khi tái lập từ Git, cần giữ nhất quán newline hoặc
kiểm tra trước/sau theo bảng này; không tự thay hash để hợp thức hóa dữ liệu.

Transcript chẩn đoán được lấy từ phần tử `<text>` của SVG nguồn, sắp baseline y
rồi x. Nó không lấy từ OCR, kết quả PDF text hay KIE gold. Bản này **chưa được
người độc lập duyệt đầy đủ**. Đã xem ảnh sạch 002 để xác nhận seller/buyer cùng
hàng và nội dung bảng/tổng không bị cắt. Ba PDF vector đều có lớp chữ; 12 PDF
image-only của tập con không có lớp chữ. Nguồn hoàn toàn không dấu tiếng Việt,
nên không đo được chất lượng nhận dạng dấu tiếng Việt.

## Chạy lại

Runtime native dùng Python 3.12 và các dependency đã ghim trong
`requirements-document-reader.txt` / `requirements-document-reader-test.txt`.
Trên máy này runtime đã có model tại
`C:/Users/ADMIN/Downloads/vietreceipt_ocr_probe/.venv/Scripts/python.exe`.

```powershell
python -m scripts.prepare_tv2_reader_manifest --source-root <checkout-PR60> --manifest <checkout-PR60>/data/vietreceipt_synthetic_v0/rendered/manifest.csv --source-commit 5e5b871dd1c7413f2d74acc175aad0f0186486f7 --output results/dev/tv2-reader-v0/inputs-new --sample-ids VRSYN-002,VRSYN-005,VRSYN-008
python -m scripts.compare_pdf_routes --manifest results/dev/tv2-reader-v0/inputs-new/manifest.json --output results/dev/tv2-reader-v0/paired-new --orientation auto
python -m scripts.verify_reader_handoff --run-dir results/dev/tv2-reader-v0/paired-new --output results/dev/tv2-reader-v0/contracts-new
```

Mỗi lượt dùng thư mục mới. Tải [ZIP evidence đầy đủ](../results/dev/tv2-reader-v0/tv3-tv2-handoff-20261023.zip)
và giải nén tại project root để có inputs/raw evidence/source snapshot. Các bảng
kết quả, verification và overlay chính cũng được theo dõi trực tiếp trong PR.
ZIP là snapshot lịch sử, giữ cả báo cáo tại thời điểm chạy trước khi có Git;
báo cáo trên nhánh PR này ghi thêm bối cảnh công bố. Gói `inputs-20261023` có thể dùng trực
tiếp làm manifest chạy lại. `source-snapshot/` lưu code thực tế trước inference;
config mỗi mode lưu package versions, source hashes, config, thời điểm và hash
manifest. Khi inference, workspace là archive không có `.git`, nên local commit là
`unavailable`; commit PR60 chỉ định nguồn dữ liệu, không giả làm commit Reader.

## Giới hạn nhãn và nghiệm thu

Ba nhãn nguồn chỉ có 8 header (7 canonical và `vat_rate`), thiếu 6 header chuẩn;
`currency` chưa gán dù VND in rõ trên các tổng. Sáu đơn vị dòng hàng ghi PRESENT
nhưng không in trên nguồn; mọi `source_block_ids` đều rỗng. Schema annotation
hiện tại vẫn chấp nhận, nhưng evaluator KIE V2 thực từ chối cả ba nhãn vì tập
header không khớp. Không dùng những nhãn này để báo KIE accuracy hay verified gold.

TV3 cung cấp raw evidence và contract checks cho TV2 liên kết source gold với đúng
receipt/run/page/block; TV2/TV4 vẫn cần sửa/QA nhãn, alignment và xác nhận evaluator.
PDF text dùng confidence N/A trong báo cáo; số 1 ở wire payload là sentinel.
Docker CLI chưa có trên máy; Linux ARM64 image/scan vẫn chưa được xác minh.
Các thử nghiệm xoay 90/180/270° và nhiều trang đã làm trên bộ diagnostic TV3 cũ,
không được gán nhầm là biến thể do TV2 bàn giao.

## Kiểm chứng phần mềm

91/91 test Reader, OCR contract, OCR W2, paired comparison, importer TV2 và KIE V2
đạt; Ruff đạt. [Log](../results/dev/tv2-reader-v0/tests-20261023.log).
CI Reader được bổ sung trigger và chạy test importer/paired comparison.
Test dùng OCR double để kiểm tra hành vi phần mềm; kết quả OCR thực được lưu riêng.


## Kết quả OCR thực

| Loại đầu vào | n | CER OCR all | CER route aware | WER route aware |
| --- | ---: | ---: | ---: | ---: |
| image_only_pdf_blur | 3 | 10.29% | 10.29% | 54.29% |
| image_only_pdf_clean | 3 | 7.57% | 7.57% | 48.10% |
| image_only_pdf_noise | 3 | 7.86% | 7.86% | 51.43% |
| image_only_pdf_skew | 3 | 33.11% | 33.11% | 62.86% |
| png_image_blur | 3 | 4.76% | 4.76% | 33.81% |
| png_image_noise | 3 | 0.97% | 0.97% | 8.10% |
| png_image_skew | 3 | 29.71% | 29.71% | 48.10% |
| rendered_png_clean | 3 | 0.78% | 0.78% | 5.71% |
| vector_pdf_clean | 3 | 0.97% | 0.00% | 0.00% |
| all | 27 | 10.67% | 10.56% | 34.71% |

Hai chế độ chạy trên cùng byte của 27 tài liệu đã khóa hash. Mẫu số micro mỗi chế độ:
9,270 ký tự và 1,890 từ,
gộp khoảng trắng, giữ case/ký tự. Cả hai mode đọc thành công 27/27 tài liệu.
Route aware có 3 trang PDF_TEXT;
PDF text confidence là N/A. Xem [comparison.json](../results/dev/tv2-reader-v0/paired-20261023/comparison.json),
[CSV](../results/dev/tv2-reader-v0/paired-20261023/comparison.csv) và
[route/timing từng trang](../results/dev/tv2-reader-v0/paired-20261023/pages.csv).

Đây là một lượt serial mỗi chế độ trên Windows CPU; lần OCR đầu có khởi tạo
model. Thời gian từng mẫu là số đo cục bộ, chưa phải phân phối latency hoặc
bằng chứng speedup ổn định. Sai khác PNG và PDF image-only còn gồm rasterization,
resampling và encoding của tài liệu; không quy hết cho thuật toán routing.

[Handoff](../results/dev/tv2-reader-v0/paired-20261023/handoff.json) giữ receipt/run IDs,
source label/SVG paths và hash, split, layout, commit dữ liệu và đường dẫn
manifest tương đối. [Contract verification](../results/dev/tv2-reader-v0/contracts-20261023/verification.json)
chạy evidence thật qua Reader, TV5 evidence validator, TV4 KIE và TV5 KIE validator.
Đây là kiểm tra provider/contract, không báo KIE accuracy.


## Ví dụ lỗi bàn giao TV4

Sáu ví dụ có receipt/run/page/block IDs, text và polygon đầy đủ trong
[failure-examples-20261023.json](../results/dev/tv2-reader-v0/failure-examples-20261023.json).
Đã đối chiếu source và xem ảnh nghiêng; chưa xác lập lỗi polygon. Các lỗi dấu câu
không tự chứng minh KIE sai; chưa thấy sai giá trị tiền/ngày/mã hóa đơn trong
các ví dụ đã chọn. E01/E02 cùng nguyên nhân thứ tự đọc, không phải hai lỗi
độc lập ở cấp dataset.

| ID | Mẫu / loại | Nội dung |
| --- | --- | --- |
| E01 | 002 skew / thứ tự header | SL, Don gia, Thanh tien xuất trước Mat hang |
| E02 | 002 skew / thứ tự dòng hàng | 72.000 xuất trước mô tả 1. So tay |
| E03 | 002 clean image-only PDF / dấu câu | Mất dấu hai chấm ở nhãn Ma hoa don |
| E04 | 002 blur image-only PDF / dấu câu | Mất dấu hai chấm ở nhãn Ngay |
| E05 | 005 clean image-only PDF / dấu câu | Mất ngoặc ở Thue VAT (10%) |
| E06 | 002 blur PNG / ký tự footer | layout_b thành 1ayout_b |


54/54 evidence/KIE runs qua cả bốn contract checks, không sửa receipt/run/block IDs.
Xem overlay [ảnh nghiêng](../results/dev/tv2-reader-v0/preview-skew-20261023/index.html),
[PDF scan](../results/dev/tv2-reader-v0/preview-scan-20261023/index.html),
[PDF text](../results/dev/tv2-reader-v0/preview-pdf-text-20261023/index.html).

Lượt inference ban đầu chạy local trước khi khôi phục Git. Bản công bố giữ nguyên
raw evidence và provenance; các kiểm tra sau khi đồng bộ main được ghi trong PR.
[Patch source](../results/dev/tv2-reader-v0/tv3-source-changes.patch) có cả phần
TV3 tại thời điểm inference trước khi đồng bộ main, đối chiếu `061960f0…`;
raw inputs/evidence nằm trong gói bàn giao riêng. Chưa đóng issue #48 vì TV2/TV4
còn phải QA/alignment gold, và TV5 cần nghiệm thu môi trường demo.
