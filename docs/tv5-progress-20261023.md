# TV5 — tiến độ tích hợp và bàn giao ngày 23/10/2026

## Đầu vào đã kiểm tra

| Thành viên | Bàn giao trên GitHub | Phần dùng được cho TV5 | Điều kiện chưa được đáp ứng |
|---|---|---|---|
| TV1 | [PR #64](https://github.com/vietreceipt-team/vietreceipt/pull/64), head `57c82e6` | Protocol dự thảo: tách source/aligned gold; giữ lỗi trong mẫu số; tách machine/human; các gate G1–G6 | Chưa co-sign/freeze; không cấp quyền mở final test hoặc công bố accuracy |
| TV2 | [PR #66](https://github.com/vietreceipt-team/vietreceipt/pull/66), head `8a60330` | Gói `tv4-dev-v1.zip`, 80 input từ 20 base, train 60/validation 20; có source bytes/hash và source regions | `PENDING_REVIEW`, reviewed_records=0; vùng nguồn và mapping chỉ là candidate. Không chuyển thành VERIFIED |
| TV3 | [PR #65](https://github.com/vietreceipt-team/vietreceipt/pull/65), head `036b775` | Báo cáo 27 validation variants × 2 route modes; evidence/IDs và 4 CI checks pass | Bằng chứng Reader/KIE diagnostic, không phải backend HTTP demo hoặc source-gold accuracy; vẫn chờ alignment QA |
| TV4 | [PR #58](https://github.com/vietreceipt-team/vietreceipt/pull/58) và [#63](https://github.com/vietreceipt-team/vietreceipt/pull/63) đã merge | KIE V2 thật và sửa chấm USD cents trong gold | UNKNOWN/strict-completion, row precision/F1 và source-region matcher chưa được bàn giao/co-sign theo [#49](https://github.com/vietreceipt-team/vietreceipt/issues/49) / protocol dự thảo |

Các PR #64/#65/#66 đang mở ở thời điểm rà soát; không merge thay phần của thành viên khác. TV5 tiếp nhận byte dữ liệu ở commit cụ thể, không lấy tên branch đang thay đổi làm phiên bản thí nghiệm.

Gói TV2 được đọc từ `8a603300071d6dbfebd23e8f22a8c9cbac90ff48`, SHA-256:
`6661c858c0564820a035ae0f62951647d19c74dd0c789aa4e56a072dfb4d9790`.
ZIP CRC đạt. Đây là kiểm tra toàn vẹn, không phải duyệt nhãn độc lập. Không mở hoặc chạy test/final mock.

## Phần TV5 bổ sung được ngay

- Importer `scripts/prepare_tv2_backend_manifest.py` kiểm tra train/validation, count/hash, đường dẫn, trùng ID và rò base/template/content. Chỉ copy toàn bộ 20 file validation; không lọc theo kết quả Reader cũ.
- Chạy HTTP từ source bytes thật, qua outbox/Redis/Celery/PostgreSQL và provider TV3/TV4 trên môi trường Docker demo đã được kiểm chứng ở [PR #62](https://github.com/vietreceipt-team/vietreceipt/pull/62). Không gọi KIE trên OCR dựng sẵn và gọi đó là end-to-end.
- Tự xuất `machine_predictions.jsonl`, `run_metadata.json`, `samples.csv`, `failures.csv`, `metrics.json`/CSV. Có error stage/code/elapsed, manifest hash và worker provenance. `accuracy=null`, NOT_SCORED.
- Giữ processing success riêng với review/export success; không biến lỗi xuất file thành lỗi AI. Không ghi đè snapshot gốc khi phát hiện response sau review bị thay đổi. Không ghi raw exception URL/text/path vào log/tóm tắt lỗi.
- Importer giữ pending QA; runner từ chối auto-review với manifest nhập này. Không ghi correction/verify lên 20 receipt validation, không dùng candidate gold để tính điểm.

## Kiểm chứng

- 347 Python tests và 181 subtests đạt trên PostgreSQL test database riêng, gồm race/concurrency; không skip race test.
- Trong đó 33 test tập trung vào reproducibility/handoff: raw vs reviewed, schema/native failure, timeout, file thiếu/hash sai, failure stage/code, export thất bại nhưng processing thành công, snapshot không ghi đè, duplicate/leak/path/final input rejection và pending QA.
- Legacy/shared contracts, Ruff, format và `git diff --check` đạt.
- Luồng JPG/PDF text/PDF scan → correction → verify → JSON/CSV/XLSX với provider thật và giới hạn ARM64: xem [nghiệm thu PR #62](v2-stability-acceptance.md). Không thay provider/Paddle hoặc sửa UI/API/storage ở đợt bổ sung này.
- Kết quả batch TV2 validation và CI của PR bổ sung sẽ được ghi sau khi chạy xong, không coi test phần mềm là accuracy.

Lệnh tái lập và ý nghĩa artifact: [v2-reproducible-demo.md](v2-reproducible-demo.md#tv2-development-handoff-and-report-tables-23-october).

## Còn mở trên issue #50

1. TV1/TV2/TV4 thống nhất protocol/mẫu số và scope “13 header + line items, tax excluded”; TV4 bổ sung UNKNOWN policy, row precision/F1, source-region matcher có test. Không dùng block-ID matching của KIE làm source-level row score.
2. TV2 cùng reviewer độc lập duyệt source gold và alignment cho đúng reader run. Receipt/run IDs của lượt backend mới khác gói Reader; không ghép ID cũ sang dự đoán mới.
3. Sau co-sign và QA, nối metric hook được duyệt với raw predictions, kiểm tra source-region path và xuất bảng accuracy thật; không thay bằng giá trị đã correction.
4. Sau freeze code/config và test độc lập, chạy final run theo TV1. Independent mock, nghiên cứu người dùng và kết luận accuracy chưa được nghiệm thu.

Issue #50 được hoàn thiện dần theo bằng chứng; các gate này vẫn mở. Không đóng issue vì CI xanh, ZIP hợp lệ, đủ file hoặc demo thành công.
