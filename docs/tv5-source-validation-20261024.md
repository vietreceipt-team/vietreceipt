# TV5 source evaluation: bàn giao và rà soát 24/10/2026

## Đã hoàn thiện code

- PR #70 dùng chính commit TV4 PR #69 đến `1e7b407`; giữ ancestry và tác giả, không copy một evaluator khác. Baseline production và config 2.1.0 giữ nguyên. Cách tích hợp đã ghi tại [trao đổi PR #69](https://github.com/vietreceipt-team/vietreceipt/pull/69#issuecomment-6382119430).
- Pin `jsonschema` thống nhất **4.26.0** trong root OCR, Reader tests, contracts và backend. OCR CI cài cả bộ cùng một lần để resolver kiểm tra đồng thời. Giữ PDF regression chạy với reportlab/pypdfium đã pin; không bỏ test để né lỗi.
- TV5 source runner kiểm source/gold/regions hashes, sample/split identity, selected receipt/attempt/OCR/KIE, worker input SHA và geometry canonical trước khi gọi kernel TV4. UNKNOWN, row P/R/F1 và failure None dùng implementation 2.2.0; không thay bằng corrected data.

## Kết quả kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| PostgreSQL backend + shared suite | **410 passed + 217 subtests**, gồm race và source-gate/one-command tests |
| Unittest discovery giống OCR CI | **184 test, OK**, PDF dependency hiện có nên regression không bị skip |
| Pip resolver chung OCR/contracts/Reader | Pass; không còn 4.23.0 vs 4.26.0 |
| Pip check | No broken requirements found |
| Runtime riêng: HTTP/outbox/Redis/Celery/PostgreSQL, Reader/KIE thật | JPG, PDF text, PDF scan **3/3 VERIFIED**, JSON/CSV/XLSX parsed |
| Hash phía worker | Cả ba khớp byte upload/source; source SHA/config/runtime lưu trong attempt |
| Machine vs human | Snapshot máy không đổi sau synthetic review; reviewed export nằm riêng |
| Gold TV2 pending | Plan 20 validation mẫu vẫn pending; scorer trả **exit 2, metrics=null, evaluated=0**, không HTTP |
| Gate identity/frame | Test từ chối hash/ID/config/frame/split sai, thiếu mẫu/QA/sign-off; có EXIF/PDF rotation và failure/lease/storage cases |

Capture runtime ở `cdeb421`, Git sạch, dùng Python 3.12 native ARM64 và đúng pinned providers. Mã AI/backend/schema/scorer giữ nguyên tới head sửa dependency `a77e1cd`; không gán lại commit cho lượt đo cũ. Worker source checksum, package versions, model hashes và timings có trong snapshot. Đây là synthetic software acceptance, không phải independent research gold hoặc final accuracy.

[Index + hash](verification/tv5-source-20261024/index.json), [CSV từng mẫu/latency](verification/tv5-source-20261024/samples.csv), [ZIP machine evidence](verification/tv5-source-20261024/machine-source-evidence.zip), [pending gate](verification/tv5-source-20261024/pending-gate.json).

## Bàn giao và phần còn chờ

TV2 PR #66 hiện ở `8928119`, thêm overlay intake v2 hash `fca8aa088b54da280dbca776b7d654c339c0d3717fb368b4a96ace2140cce223`; kiểm ZIP hash/CRC đạt. Overlay trỏ cùng base ZIP hash `6661c858…` và không đổi source/evidence/gold; 80 mẫu vẫn PENDING_REVIEW. Queue/phiếu và manifest mới không thay thế reviewer thật.

TV1 PR #64 hiện có quyết định đề xuất D1–D5 và acceptance tracker; vẫn cần co-sign. Positive-IoU matcher chỉ là development candidate: tiny overlap/broad boxes/cropped frames và chính sách cuối cần TV4/TV1/TV2 nghiệm thu, không suy ra scientifically validated từ test xanh.

Người review cần duyệt source gold/regions, alignment cho đúng run và hash; TV3 xác nhận version/config/coordinate contract. Sau đó TV1/TV2/TV4/TV5 ghi đồng thuận thật và worker/config fingerprint vào **plan mới**. Không ký thay người khác hoặc sửa QA flag để vượt gate. Source-level không dùng gold OCR block IDs; aligned KIE A/B có manifest/experiment riêng.

Lệnh tạo pending plan và one-command evaluation: [TV5 source guide](tv5-source-evaluation.md). Khi đủ điều kiện, runner xuất raw machine predictions, per-sample source JSON/CSV, failures, latency và provenance. Khi chưa đủ, báo NOT_SCORED/null. Independent mock/final freeze và project research acceptance vẫn mở; giới hạn Paddle Linux ARM64 không được coi là đã sửa.
