# TV3 — Kết quả cục bộ cho issue #48, ngày 23/10/2026

Đã hoàn thiện công cụ so sánh và chạy OCR thật trên Windows CPU. Báo cáo bên dưới
giữ kết quả diagnostic của lượt chạy trước khi khôi phục Git, nay được công bố
cùng PR TV3. [ZIP chẩn đoán gốc](../results/dev/document-reader-v2/tv3-diagnostics-20261023.zip)
giữ raw runs và code snapshot. Đây là kết quả diagnostic
TV3 ban đầu. Đã tiếp nhận dữ liệu render mới của TV2 ở PR60 và thực hiện
[lượt tiếp theo riêng](tv3-tv2-synthetic-v0.md); nghiệm thu gold liên thành viên
vẫn cần hoàn tất, không đánh dấu toàn bộ #48 là DONE.

## Phạm vi đã làm

- `scripts/compare_pdf_routes.py`: chạy `ocr_all` và `route_aware` trên cùng byte
  đầu vào, kiểm tra SHA-256, giữ mọi mẫu lỗi và ghi CER/WER, số ký tự mất/thay/chèn.
- Reader ghi route, lý do fallback, thời gian đọc PDF/render/orientation/OCR và
  phép biến đổi tọa độ trong metadata riêng, giữ nguyên contract evidence.
- `ocr_all` bỏ qua hẳn lớp chữ PDF. PDF direct text được báo confidence `N/A`;
  giá trị 1.0 trong wire payload chỉ là sentinel tương thích.
- Bổ sung ảnh nghiêng 7°, PDF chữ hai trang và PDF scan hai trang vào fixture
  development. Giữ cả PDF mixed, ảnh mờ/nhiễu/phối cảnh và xoay 90/180/270°.
- `scripts/verify_reader_handoff.py`: đưa evidence thật qua Reader contract,
  TV5 evidence validator, TV4 KIE và TV5 KIE validator, không sửa ID thủ công.
- Xuất sáu ví dụ lỗi được phân loại, hai evidence mẫu PDF chữ/ảnh, metadata,
  phiên bản package, hash nguồn/dữ liệu/model và hướng dẫn bàn giao.

## Kết quả chẩn đoán thật

Dữ liệu `tv3-synthetic-diagnostics` **v1.1, development**: 14 tài liệu đọc được
và 1 PDF hỏng có chủ đích. Tất cả biến thể dùng **một mẫu bố cục giả lập**,
không phải tập TV2 hay đánh giá cuối. Mẫu số micro: 5.545 ký tự, 1.088 từ sau
gộp khoảng trắng. Giữ nguyên dấu tiếng Việt và chữ hoa/thường.

| Nhóm đầu vào | Số tài liệu | CER OCR all | CER route aware | WER route aware |
| --- | ---: | ---: | ---: | ---: |
| PDF chữ 1 trang | 1 | 16,26% | 0,00% | 0,00% |
| PDF chữ 2 trang | 1 | 16,23% | 0,00% | 0,00% |
| PNG sạch | 1 | 15,95% | 15,95% | 64,06% |
| JPEG nén | 1 | 19,63% | 19,63% | 71,88% |
| Ảnh mờ | 1 | 16,87% | 16,87% | 68,75% |
| Ảnh nghiêng 7° | 1 | 30,06% | 30,06% | 76,56% |
| Nhiễu | 1 | 15,95% | 15,95% | 64,06% |
| Phối cảnh | 1 | 15,34% | 15,34% | 62,50% |
| PDF scan 1 trang | 1 | 16,26% | 16,26% | 64,06% |
| PDF scan 2 trang | 1 | 16,23% | 16,23% | 64,06% |
| PDF mixed 2 trang | 1 | 16,23% | 8,12% | 32,03% |
| Xoay 90/180/270° | 3 | 15,95% | 15,95% | 64,06% |
| Toàn bộ tài liệu có tham chiếu | 14 | **17,15%** | **13,33%** | **50,37%** |

WER của `ocr_all` toàn bộ là 65,44%. Cả hai chế độ đọc thành công 14/14 tài liệu
hợp lệ; PDF hỏng trả đúng `PDF_READ_FAILED` ở cả hai. Mẫu PDF hỏng không có
transcription nên không đưa vào mẫu số CER/WER. Lần chạy đầu trong sandbox lỗi
khởi tạo font Paddle, được giữ riêng trong `local-paired-20261023`; các con số
trên chỉ lấy từ lần chạy native thành công `local-paired-native-20261023`.

Thời gian một lượt: PDF chữ 1 trang 26.806 ms OCR all (có khởi tạo model) so
với 35 ms đọc trực tiếp; PDF chữ 2 trang 30.970 ms so với 52 ms; PDF mixed
30.375 ms so với 15.213 ms. Các thời gian này mô tả lần chạy cục bộ, không phải
ước lượng speedup ổn định hay phân phối latency. Có hoạt động kiểm thử song song
trên máy; cần nhiều lần chạy và kiểm soát tải khi báo cáo hiệu năng chính thức.

## Lỗi điển hình bàn giao TV4

Chi tiết actual text, receipt/run UUID, page, block ID, reading order và polygon
nằm trong [failure-examples-20261023.json](../results/dev/document-reader-v2/failure-examples-20261023.json).

| ID | Mẫu | Loại lỗi | Ảnh hưởng cần kiểm tra |
| --- | --- | --- | --- |
| E01 | PNG sạch | Mất dấu tên người bán | Đối chiếu seller name; không suy ra text đúng vì số tiền đúng |
| E02 | JPEG | Dính nhãn thuế/dấu phân cách/số tiền | KIE có thể không nhận ra nhãn thuế |
| E03 | Ảnh mờ | Nhận nhầm nhãn ngày thành ký tự `@` | Chữ số ngày còn đúng nhưng nhãn lỗi |
| E04 | Ảnh nghiêng | Đảo thứ tự header bảng | “Thành tiền” xuất hiện trước “Tên hàng” |
| E05 | Ảnh nghiêng | Đảo thứ tự ô dòng hàng | Giá xuất hiện trước mô tả, ảnh hưởng ghép hàng |
| E06 | PDF scan | Sai dấu nhãn số hóa đơn | Số `00001234` còn nguyên, nhãn bị hỏng |

Đã nhìn nguồn ảnh nghiêng để xác nhận thứ tự bảng. Chưa xác lập lỗi geometry;
không gán nguyên nhân sai tọa độ chỉ từ CER. Mở
`results/dev/document-reader-v2/local-review-tilt-20261023/index.html` để đối chiếu
nguồn, polygon và danh sách block. Giữ nguyên raw OCR khi bàn giao.

## Kiểm chứng

- **81/81** test Reader, OCR contract, OCR W2, paired comparison và KIE V2 đạt.
  Log: `results/dev/document-reader-v2/local-tests-20261023.log`.
- **28/28** evidence/KIE run (14 mẫu × 2 chế độ) qua cả validator TV3/TV4/TV5,
  không đổi ID. Đây là xác minh provider/contract, **không phải KIE accuracy**.
  [Log cấu trúc](../results/dev/document-reader-v2/handoff-verification-20261023.json).
- Khi mở rộng sang bộ test KIE evaluator, có 2 test không đạt vì evaluator bắt
  buộc `git rev-parse HEAD` nhưng archive hiện tại không có `.git`. Không sửa
  evaluator hay giả commit để né điều kiện provenance. Bộ mở rộng đó đạt 53/55.
- Git commit cục bộ: không có. Remote main đã đọc là
  `061960f0e38549f27b3183ebc3008c58ef0e5570`. Hash thực tế và source snapshot
  của lần inference được lưu riêng; không nhận remote commit làm commit của
  code đã sửa. [Provenance](../results/dev/document-reader-v2/provenance-20261023.json).
- Docker CLI không có trên máy, nên chưa chạy Docker smoke. Giới hạn Paddle
  SIGSEGV ảnh/scan trên Linux ARM64 đã được tài liệu backend ghi nhận và vẫn
  phải coi là chưa giải quyết.

## File để xem và chạy tiếp

- [Script so sánh](../scripts/compare_pdf_routes.py).
- [Bảng paired JSON](../results/dev/document-reader-v2/paired-comparison-20261023.json)
  và [CSV](../results/dev/document-reader-v2/paired-comparison-20261023.csv).
- [Route và stage latency từng trang](../results/dev/document-reader-v2/page-routes-20261023.csv).
- [Evidence PDF chữ](../results/dev/document-reader-v2/evidence-pdf-text-20261023.json)
  và [evidence ảnh OCR](../results/dev/document-reader-v2/evidence-image-ocr-20261023.json).
- [Quy trình bàn giao, tọa độ và runtime](tv3-issue48-handoff.md).
- `results/dev/document-reader-v2/tv3-issue48-local.patch`: bản thay đổi cục bộ
  so với remote main để review/áp dụng lại trên checkout Git sau này.

TV2 đã bàn giao PNG/PDF development và đã có lượt chạy riêng trong báo cáo mới.
Để hoàn tất nghiệm thu #48, cần transcription/source gold được TV2 QA và liên kết
với evidence thật, rồi TV4 xác nhận evaluator. Final test vẫn giữ khóa. Docker và demo
toàn hệ thống cần TV5 kiểm tra trên môi trường triển khai thực tế.
