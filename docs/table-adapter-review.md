# Review chéo adapter Table của Đồng — PR #76

Ngày 03/11/2026. PR được đọc ở commit
`ad442a809e1b276417e8b7b24529f480059763eb` trên `feat/table-extraction`.
Đây là review mã và kiểm thử local, không phải approval thay tác giả hoặc reviewer
GitHub. Không sửa, push, merge hoặc gửi comment vào nhánh của Đồng.

## Phạm vi đã xem

- `ai/table/extractor.py`: evidence validation, page/bbox, block containment,
  dispatch baseline/interval, identity và intermediate metadata.
- `ai/table/pipeline.py`: thứ tự vùng, phát hiện overlap, no-row failure,
  line ID sau ghép; wrapper gọi invoice provider.
- Thay đổi `ai/kie/v2/__init__.py`: loại evidence trong vùng khỏi header candidates,
  trích currency trước khi chuẩn hóa tiền, ghép dòng trước consistency/validation,
  metadata pipeline riêng, worker entry point giữ baseline.
- Tests Table/regions/pipeline/Reader và tài liệu `docs/table-work-split.md`.

## Bằng chứng chạy

Tạo bản sao từ `git archive origin/feat/table-extraction` trong thư mục tạm của
virtualenv, sau đó chỉ chép module/fixtures/tests của strategy mới vào bản sao để
kiểm xung đột import/package. Không thay checkout chính hoặc nhánh của Đồng.

```powershell
python -m unittest tests.test_kie_table tests.test_kie_table_pipeline tests.test_kie_v2_reader tests.test_kie_table_structure -q
```

**34/34 test đạt**: 10 adapter + 7 pipeline + 2 Reader của PR #76 + 15 structure.
Chạy với Python 3.13.7/PDFium thật. Strategy chưa được dispatch trong adapter;
kết quả này xác nhận tests cùng tồn tại, không chứng minh tích hợp strategy mới.

## Kết luận kỹ thuật

Không phát hiện lỗi chặn trong phạm vi mã/test đã xem. Các ranh giới sau phù hợp
với yêu cầu #75: tọa độ trang gốc, không clip evidence, kiểm page/bbox hữu hạn,
giữ source ID/text, từ chối vùng overlap, no-row làm invoice pipeline thất bại,
line ID toàn invoice duy nhất và consistency sau khi ghép. Kiểm thử xác nhận
currency note trong vùng Table không trở thành currency header của invoice.

Điều kiện chưa được chứng minh: provider Layout dự đoán, crop OCR remapping,
gold/source review độc lập, scan/OCR thật và accuracy. Baseline/interval cần header
nhận diện được; trang không có header chưa được coi là đã hỗ trợ. Đây cũng là giới
hạn strategy mới, không phải bằng chứng để mặc định chuyển cấu hình.

## Handoff trước khi ghép strategy

1. Giữ `grouping` cũ và default hiện tại. Callback đề xuất là
   `structure_rows(selected_blocks, currency=currency, strategy=...)` ở module
   `ai.table.structure`, với block đã validate/region-select bởi adapter.
2. Đồng xác nhận tham số dispatch và identity/version của intermediate + toàn
   pipeline. Không gắn metadata baseline lên output strategy mới hoặc tự thêm
   tên strategy vào evaluator/schema trong PR thuật toán này.
3. Dùng review metadata và `unassigned_block_ids` để lưu vùng không giải quyết;
   không biến một trang không header thành bảng rỗng thành công.
4. Sau khi dispatch được bổ sung trong PR riêng, chạy lại tests vùng/nhiều vùng/
   nhiều trang, source invariants, consistency sau ghép và shared contracts.
   Sau đó mới đánh giá paired trên development gold đã QA.

Chưa có xác nhận giao diện từ Đồng; chưa gọi trạng thái này là đã tích hợp hoặc
đã được peer approval. Yêu cầu phối hợp còn lại ghi ở
[báo cáo đánh giá](table-structure-evaluation.md).
