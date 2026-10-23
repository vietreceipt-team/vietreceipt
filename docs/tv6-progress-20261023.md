# TV6 — tiến độ kiểm tra hóa đơn và bàn giao ngày 23/10/2026

## Đầu vào đã kiểm tra

| Nguồn | Phần tiếp nhận | Giới hạn |
|---|---|---|
| [Issue #51](https://github.com/vietreceipt-team/vietreceipt/issues/51) | Review đúng trạng thái, click nguồn, sửa/409/verify/export, thử nghiệm tự nguyện | Nghiệm thu cần bằng chứng trình duyệt trên provider thật |
| [Issue #59](https://github.com/vietreceipt-team/vietreceipt/issues/59) | Ba nguồn đầu vào, tách machine/reviewed, tái lập bằng commit và cấu hình | Không suy ra accuracy hoặc tiết kiệm thời gian từ smoke test |
| PR #54 đã merge | Frontend V2 và contract tests | Bộ test cũ dùng HTTP provider kiểm thử |
| PR #62/#67 đã merge | Backend thật, immutable machine-results, Reader/KIE callable, xuất dữ liệu | Bằng chứng TV5 là HTTP; không thay bằng chứng tương tác UI của TV6 |
| TV1 PR #64 | Protocol dự thảo và điều kiện pilot | Chưa có người tham gia, co-sign hay kết quả nghiên cứu |
| TV2 #66 / TV3 #65 | Dữ liệu development và chẩn đoán Reader | Không mở final/test, không merge các nhánh của thành viên khác |

Mã nền: `main` tại `0f974abd1887f9f0bf9014eabb66cc3e48684cbb`.

## Phần TV6 bổ sung

- Viewer chờ evidence sẵn sàng trước khi chọn vùng; dùng `page_index` thực, giữ trang thiếu. Chọn trường/dòng tự chuyển trang và cuộn **trong viewer** tới vùng nguồn; zoom/xoay vẫn giữ vùng thấy được. Click vùng nguồn chọn lại trường liên quan.
- Mỗi header/ô dòng/ô thuế hiển thị trạng thái PRESENT/NOT_PRESENT/UNKNOWN/AMBIGUOUS/UNREADABLE bằng tiếng Việt cùng nhãn “Dự đoán máy” hoặc “Đã đối chiếu”. Có giá trị không đồng nghĩa đã được người dùng kiểm tra. Inspector giữ máy đọc và người sửa riêng.
- Giữ null và trạng thái thiếu/khó đọc; chuyển sang PRESENT mà để trống bị chặn. Mutation có kết quả không chắc chắn (mất mạng/5xx/2xx sai contract) khóa ghi tiếp và yêu cầu tải bản mới; không replay ngầm.
- Thử nghiệm V2 chỉ bắt đầu sau đồng ý rõ ràng trên hóa đơn giả. Chỉ giữ số lần sửa/xác nhận theo loại trường, thời gian hoạt động và outcome trong bộ nhớ trang. Loại thời gian tab ẩn và chờ correction/reload/verify; không chứa nội dung hóa đơn, receipt/row/participant ID. Rút đồng ý xóa bộ đếm; tải lại trang cũng mất số liệu.
- Thêm fixture và bộ Playwright riêng dùng API/PostgreSQL/Redis/Celery/TV3/TV4 thật, không chặn HTTP: 3 định dạng và PDF challenge hai trang. Lưu nguồn/hash, machine trước/sau, bản review, lịch sử, ảnh/video, JSON/CSV ZIP/XLSX và provenance.

## Kiểm chứng

| Phép kiểm | Kết quả tại thời điểm bàn giao ban đầu |
|---|---|
| `npm ci` | Đạt, audit 0 vulnerabilities |
| `npm run typecheck` | Đạt |
| `npm test` | 58/58 đạt |
| `npm run lint`, `npm run build` | Đạt |
| `npm run test:e2e` | 30/30 đạt; HTTP provider kiểm thử |
| PDF trang 2, dòng 60 ở cuối trang, zoom/xoay | Đạt trong browser provider test; ảnh `v2-long-table-source.png` |
| Bốn trạng thái null + PRESENT sai OCR | Đạt; không tự PATCH/xác nhận, không ghi đè machine |
| Consent/rút đồng ý, response mất và evidence tải chậm | Đạt bằng unit/browser tests |
| Browser provider thật | **4/4 đạt**: JPG, PDF chữ, PDF scan, PDF challenge hai trang; [run 39968756494](https://github.com/vietreceipt-team/vietreceipt/actions/runs/39968756494) |

Máy phát triển Windows dùng Node 24.19.0/Python 3.13.7, không có Docker/WSL hoặc Python 3.12. Lượt nghiệm thu thật chạy trên GitHub Ubuntu x86_64/Python **3.12.15**, PostgreSQL/Redis/Celery riêng, reader `ai.document_reader.backend:read_document` và KIE `ai.kie.v2:extract_invoice`. Provider/callable, package/model/config và source hash có trong machine attempts. Không coi test provider là bằng chứng AI thật.

## Kết quả trình duyệt trên provider thật

| Đầu vào | Nguồn → đối chiếu → 409 thật → sửa → VERIFIED | JSON / CSV ZIP / XLSX | Machine trước/sau |
|---|---|---|---|
| JPG | Đạt; 1 dòng hàng | Nội dung đã parse, giữ `00001234` | Giữ nguyên |
| PDF chữ | Đạt; 1 dòng hàng | Nội dung đã parse, giữ `00001234` | Giữ nguyên |
| PDF scan | Đạt; 1 dòng hàng | Nội dung đã parse, giữ `00001234` | Giữ nguyên |
| PDF challenge 2 trang | Đạt; 12 dòng, chọn dòng chuyển trang 2 | Giữ UNREADABLE/null và số đã sửa | Giữ nguyên |

Challenge có lỗi **thực từ KIE**: `invoice_number` là PRESENT với `00001234 COPY`, người dùng đối chiếu ghi chú bản sao trên nguồn rồi sửa thành `00001234`. `invoice_symbol` là UNREADABLE/null, được đối chiếu và giữ nguyên trạng thái này qua verify và cả ba định dạng xuất; không đoán phần bị che. `buyer_tax_id` là NOT_PRESENT/null, tách rõ khỏi trường không đọc được. Các correction header/dòng/thuế đi qua UI; request cạnh tranh của phiên thứ hai cố ý tạo 409, UI giữ draft, reload rồi lưu version mới.

Runner và worker ghi merge commit `207e93e7b1f7269afe6604b2d8fe8254c3464172`, `git_dirty=false`, source hash `0521bf3fff26604557f2c5be20afd0274e3e0b86d88b8123a0460864fb5581cd`; PR branch head lúc chạy là `d39f07c14334a4c677523fb154e783aa698a1204`. Không gán ngược commit báo cáo cho inference đã chạy.

- [Artifact CI, ảnh/video và service logs](https://github.com/vietreceipt-team/vietreceipt/actions/runs/39968756494/artifacts/12508132228).
- [Bản lưu lâu dài 75 file nguồn/bằng chứng](verification/tv6-20261023/browser-evidence.zip), [index/hash ledger](verification/tv6-20261023/index.json), [bảng 4 mẫu](verification/tv6-20261023/samples.csv), [metrics](verification/tv6-20261023/metrics.json).
- [JPG](verification/tv6-20261023/jpg-review.png), [PDF chữ](verification/tv6-20261023/text_pdf-review.png), [PDF scan](verification/tv6-20261023/scan_pdf-review.png), [lỗi PRESENT và UNREADABLE của challenge](verification/tv6-20261023/challenge-review.png).

ZIP SHA-256: `ac02de95a3c4c299bae035f9dd7e1d86fc72155d06e2e600c586cc8e645fcd0d`. Đã kiểm tra CRC, mọi hash nguồn, machine trước/sau, JSON, CSV và cấu trúc XLSX sau khi tải từ CI. ZIP giữ nguyên byte của artifacts; chỉ có dữ liệu giả. CI frontend trên cùng head: [run 39968756287](https://github.com/vietreceipt-team/vietreceipt/actions/runs/39968756287), 58 unit + 30 browser tests đạt.

Lịch sử nghiệm thu giữ nguyên: [run đầu](https://github.com/vietreceipt-team/vietreceipt/actions/runs/39967076512) thất bại vì test đọc upload body sau navigation; [run tiếp](https://github.com/vietreceipt-team/vietreceipt/actions/runs/39967561163) được hủy để sửa chờ UI không giới hạn. Run đạt bên trên chạy mới cả 4 mẫu sau sửa, không lấy mẫu thành công của các lượt khác ghép thành 4/4. Video là browser tự động, **không phải người tham gia nghiên cứu**.

## Còn mở trên issue #51

1. TV1 cùng TV6 duyệt protocol, tuyển người tự nguyện và chạy manual/assisted có counterbalance trên mock. Worksheet chưa có dữ liệu người tham gia. Cần chấm final correctness riêng bằng đáp án đã duyệt; không dùng trạng thái VERIFIED làm accuracy.
2. TV1/leader nghiệm thu UI và bộ ảnh/video/provider thật; review PR trước merge. Không tự merge hoặc đóng issue chỉ vì CI xanh.
3. Kết quả demo synthetic chỉ chứng minh luồng thao tác trên số mẫu đã ghi, không chứng minh unseen-template accuracy, hiệu suất hay phần trăm tiết kiệm thời gian.

Lệnh chạy và artifact: [hướng dẫn TV6](tv6-review-demo.md). Thiết kế pilot: [protocol và worksheet](tv6-pilot-protocol.md).
