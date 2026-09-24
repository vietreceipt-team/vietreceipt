# VietReceipt Testing and Evaluation

Thư mục này chứa kiểm thử phần mềm và các regression/contract tests phục vụ hệ thống VietReceipt.

## Hai lớp kiểm thử phải tách biệt

### 1. Software correctness
Mục tiêu: hệ thống chạy đúng theo contract.

Bao gồm:
- unit tests;
- integration tests;
- API/contract tests;
- frontend tests;
- error handling;
- state transitions;
- schema validation;
- export validity.

### 2. Research evaluation
Mục tiêu: trả lời các research questions trong `docs/research-design.md`.

Bao gồm:
- end-to-end invoice metrics;
- seen vs unseen-template evaluation;
- robustness slices;
- OCR-all vs route-aware baseline;
- line-item grouping experiment;
- normalization/check ablation;
- independent mock final test;
- latency and stage-failure measurements.

**Unit test pass không phải bằng chứng về model/system accuracy.**
**Validation accuracy không thay thế frozen final-test accuracy.**

## Luồng phần mềm quan trọng cần kiểm thử

- tải ảnh/PDF lên hệ thống;
- route PDF text vs scan/image correctly;
- OCR;
- trích xuất header;
- nhóm line items;
- normalization / consistency checks;
- chỉnh sửa thông tin;
- xác nhận hóa đơn;
- lưu lịch sử chỉnh sửa;
- source evidence highlighting;
- xuất JSON/CSV/XLSX;
- xử lý lỗi khi OCR/KIE thất bại;
- xử lý file không hợp lệ.

## V2 contract priorities

Current legacy v1 contract tests remain until migration is complete.

Before v1 removal, add v2 tests that validate:
- all canonical v2 header fields;
- tax breakdown;
- row-level line items;
- PRESENT / NOT_PRESENT / UNREADABLE / AMBIGUOUS / UNKNOWN semantics;
- evidence block linkage;
- direct PDF and OCR paths converging to the same KIE contract;
- correction preserving immutable machine output;
- export keeping header and line-item tables structurally linked.

## Final evaluation safeguards

The final evaluation runner must fail closed when:
- the requested frozen manifest is missing;
- sample provenance is incomplete;
- a test sample belongs to a development template;
- a derived/augmented sibling crosses splits;
- expected samples are missing;
- configuration/commit metadata is absent.

It must never fabricate metrics from partial or unverified data.

## Reproducibility record

Every formal benchmark output should record:
- git commit;
- dataset family and snapshot;
- manifest/split version;
- template seen/unseen label;
- config version;
- evaluated/missing counts;
- per-stage failures;
- metric definitions.

## Thành viên phụ trách chính

Đặng Quang Trung — DevOps, QA và phân tích hệ thống

TV1/TV2/TV3/TV4 jointly own the **research evaluation definition**; QA owns repeatable execution and release evidence.

## Nguyên tắc

- Mỗi lỗi đã sửa nên có kiểm thử tương ứng nếu phù hợp.
- Các API quan trọng phải có kiểm thử.
- Không chỉ kiểm thử trường hợp chạy đúng.
- Phải có kiểm thử cho trường hợp lỗi.
- Kết quả kiểm thử phải có bằng chứng khi dùng để nghiệm thu task.
- Mọi thay đổi contract phải cập nhật schema, API, examples và consumer tests cùng nhau.
- Không tune sau khi xem final test mà vẫn gọi tập đó là untouched final test.
