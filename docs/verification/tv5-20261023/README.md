# TV5 synthetic development capture — 23/10/2026

Xem [index.json](index.json) để lấy count, commit/dirty, worker identity và SHA-256; [machine-evidence.zip](machine-evidence.zip) chứa đầy đủ kết quả và các source synthetic cần chạy lại. Các CSV/JSON bên ngoài ZIP là bản sao nguyên byte để xem nhanh trên GitHub.

- docker-validation: 20 file TV2 validation, một family/5 base, pending QA, chỉ NEEDS_REVIEW; exploratory runner dirty=true được giữ nguyên.
- native-validation: lặp đúng cùng 20 source với runner f17581f clean, chỉ NEEDS_REVIEW. Không cộng hai runtime thành 40 mẫu độc lập.
- native-three-route: một invoice giả, 3 định dạng JPG/PDF text/PDF scan, auto-review synthetic tách reviewed/; không phải accuracy.
- negative-challenges: corrupt/missing/hash mismatch, đủ 3 lỗi và exit 1; cohort challenge riêng.

`machine_predictions.jsonl` chỉ chứa attempt và OCR/KIE gốc. `samples.csv`/`failures.csv` không chứa raw exception URL/text/path. Raw machine JSON cố ý chứa chữ trên hóa đơn giả để đối chiếu. `accuracy=null`, NOT_SCORED cho mọi run.

Không đổi các run/metadata gốc. ZIP TV2 nguồn ở PR #66 có hash riêng trong index; importer chỉ lấy validation, không copy gold/evidence cũ, không chạy final/test. Lệnh dựng lại: [v2-reproducible-demo.md](../../v2-reproducible-demo.md). Trạng thái/phụ thuộc: [TV5 status](../../tv5-progress-20261023.md).
