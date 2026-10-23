# TV2: đối chiếu #47 và feedback #60

Ngày kiểm tra: 23/10/2026. Nhánh sửa: codex/47-tv2-dataset-completion.
Đối chiếu #47, review kỹ thuật #60 và phụ thuộc chặng 1/2 trong #59.
Đây là báo cáo nghiệm thu cục bộ, không thay cho lead review/merge.

## Feedback lead #60

| Feedback | Xử lý và bằng chứng |
| --- | --- |
| Thiếu 13 header, thừa vat_rate | Generator xuất đúng 13 header. VAT là metadata hiển thị, không thêm header ngoài chuẩn; field không in dùng UNKNOWN/null. |
| Nhãn unit không xuất hiện trên ảnh | PDF/SVG có cột ĐVT. Cùng render specification tạo transcript và source gold; test sửa sai unit phải bị QA bắt. |
| Không có source_block_ids thật | Giữ source gold chưa liên kết; thêm công cụ áp mapping đã review, kiểm tra hash/ID/block và gọi validate_gold trên bản sao. Không tự tạo OCR ID hoặc nhận source gold là verified. |
| Chỉ SVG, chưa reader thật | Có PDF chữ, PNG, PDF scan. Ba luồng reader thực và KIE thực đều PASS schema. Xem verification/reader/report.json. |
| Ba layout gần giống, chỉ smoke-test | Có sáu họ bố cục, khổ giấy/khối thông tin/bảng/tổng tiền khác nhau; split theo family trước augmentation. Vẫn là bộ dev từ một generator, chưa có independent mock final test. |
| Thiếu tests | 102 test dataset/KIE/reader PASS; Ruff PASS; toàn bộ 30 mẫu/510 file qua QA. Tests gồm corruption, arithmetic, leakage, checksum, visible-vs-gold, determinism, PDF text/reader, mapping và evidence-link gate. |

Ba luồng thực là PDF_TEXT, IMAGE_OCR, PDF_OCR. Đây là kiểm thử chức năng
reader/KIE, accuracy vẫn null; không công bố như kết quả đánh giá cuối.

## Deliverables #47

| Nhóm | Hiện trạng |
| --- | --- |
| A. Registry | Đã có datasets.yaml, source/license/task/snapshot/count/status. CORD và Vietnamese đã audit subset thật; SROIE còn access/archive. |
| B. Preparation | Downloader HF theo commit/shard/checksum, adapter ba nguồn, giữ native labels/official split, báo mẫu bị từ chối. SROIE cần archive được phép dùng. |
| C. Mapping | YAML version + executable mapping; không suy diễn tax ID; runner public riêng chỉ tính supported PRESENT cells và yêu cầu evidence đã review. |
| D. Synthetic | 30 mẫu gốc, sáu layout, 13 header, 1–12 dòng, VAT 0/5/8/10, missing buyer, PDF/PNG/SVG, transcript và ground truth đồng bộ. |
| E. Manifests | Base + train/validation/test + 510 variant rows; parent, provenance, checksum; JSON runner TV3 riêng từng split. |
| F. Validation | Schema, 13 keys, status/value, arithmetic, duplicate IDs/content, file integrity, checksum, family/base leakage, visible-label-transcript. |
| G. Evaluation support | Manifest/reference cho TV3; reader/KIE thật trên ba route; công cụ link evidence sau review; exporter bảng từ evaluator thật. Chưa có verified final gold/predictions để xuất accuracy cuối. |
| H. Final test | Có policy, freeze tool có kiểm tra điều kiện và hướng dẫn intake independent mock. Chưa freeze bất kỳ bộ dev nào. |

## Nguồn đề xuất và subset thật

- Vietnamese Bill Extraction: minhduc168/dataset-origin-vlm-extract-bill,
  snapshot d24586e71318dec13c69f5f35f3d8bc04c5e561c. Card khai báo MIT.
  Đã tải/audit/map 10/10 native train samples.
- CORD: naver-clova-ix/cord-v2, snapshot
  7f0115a4b758a71d6473b8d085751692da2fef98. CC-BY-4.0.
  Audit 10 train samples; map 7, từ chối 3 giá trị cần review.
- SROIE: ban tổ chức ICDAR 2019. Chưa truy cập được official download/terms
  trong phiên này; chưa bịa version, checksum hay usable count.

Chi tiết tải lại và mapping: data/registry/README.md.
Ảnh public/native labels chỉ nằm trong data/raw và data/processed bị Git ignore.

## Chưa được đánh dấu hoàn thành #47

1. Lấy archive SROIE chính thức và ghi lại điều kiện truy cập/checksum; chạy
   adapter/subset thật, giữ native OCR labels.
2. Lead chốt bộ nguồn đề xuất, phạm vi subset và protocol; mở rộng public data
   sau audit. 10 mẫu là kiểm tra adapter, không phải benchmark đầy đủ.
3. Người review kiểm tra nhãn nguồn và mapping block trên evidence thật.
   Công cụ có sẵn nhưng không tự ghi tên người review hoặc approved=true.
4. Tạo independent mock set do người khác thiết kế/annotate; có review độc lập.
   Không thể đổi tên output generator thành independent test.
5. TV1/TV3/TV4 chốt cấu hình, freeze manifest mới trước final tuning và chạy
   đánh giá thật: per-field, row/cell, complete invoice, per-dataset/robustness.
6. TV4 review protocol của runner public có mask trước khi chạy benchmark
   chính thức; không đưa UNKNOWN unsupported vào mẫu số lỗi.
7. Clone/reproduce trên máy thứ hai và lead review/merge. CI workflow đã thêm
   nhưng chưa chạy trên GitHub trong phiên này.

Vì vậy, phần sửa code/gói dev bàn giao TV3 đã có bằng chứng cục bộ; không ghi
“hoàn thành toàn bộ #47”, không đóng issue, không freeze bộ dữ liệu đã xem.

## Tái tạo và môi trường

Xem docs/tv2-synthetic-v0.md và requirements-data*.txt.
Windows CPU; font Arial có hash trong generation.json; PDFium 5.12.1,
PaddleOCR/PaddleX 3.0.3 và PaddlePaddle 3.0.0.
Lần chạy thật dùng cache model ở đường dẫn không dấu: Paddle không mở được
inference.json trong đường dẫn chứa “nhóm 2”. Không sửa runtime chung của TV3;
thiết lập PADDLE_PDX_CACHE_HOME tới một đường dẫn ASCII có quyền ghi.

verification/ lưu QA, statistics, log tests, snapshot audit và reader evidence/
KIE outputs thật. git_dirty=true trong report phản ánh code chưa commit lúc chạy.
Raw artifacts và version/hashes được giữ để review, không thay bằng con số accuracy.
