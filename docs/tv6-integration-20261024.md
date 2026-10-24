# TV6 — kiểm tra integration và chuẩn bị demo ngày 24/10/2026

## Phạm vi theo review

Ưu tiên ổn định Frontend hiện có: đồng bộ các dependency đã merge, chạy lại luồng thật và chuẩn bị kịch bản/bằng chứng bảo vệ. Không thêm tính năng giao diện hoặc đổi thuật toán. Nội dung review người dùng cung cấp được dùng làm yêu cầu; bản protocol/worksheet vẫn chờ TV1 chốt thiết kế nghiên cứu.

## Mã nền được kiểm tra

| Thành phần | Trạng thái khi bắt đầu | Phạm vi tiếp nhận |
|---|---|---|
| `main` | `07c7cd00b0a12a555ec98f1ba45c7d1f1584e5eb` | Đã merge vào nhánh PR #68, không đẩy trực tiếp main |
| Backend #70 | Đã merge 24/10 | Worker ghi SHA-256/MIME/số byte của nguồn; source-evaluation tooling |
| KIE #69 | Đã merge 24/10 | Grouping/evaluator mới; production grouping mặc định vẫn baseline |
| Reader #65 | Còn mở | Không lấy code chưa merge vào lượt integration này |
| KIE follow-up #71 | Còn mở | Theo dõi cho lần kiểm tra sau merge |

Không mở final/test hoặc dùng pending gold để chấm accuracy. Backend source-evaluation mới là phạm vi TV5/TV4; TV6 kiểm tra hợp đồng và luồng UI, không tự duyệt gate nghiên cứu.

## Kiểm tra cần đạt trên mã nền mới

- Typecheck, lint, build, 58 unit tests và 30 browser tests của Frontend hiện có.
- 4 browser E2E với provider canonical: JPG, PDF chữ, PDF scan và PDF challenge hai trang.
- Worker input identity khớp SHA-256, MIME và số byte của file upload — kiểm tra trực tiếp metadata mới từ #70.
- Review header/dòng/thuế, nguồn nhiều trang, 409 thật và reload giữ draft, verify, export và immutable machine snapshot.
- Challenge giữ machine PRESENT sai trước sửa, ảnh inspector sau sửa và video kết quả cuối. UNREADABLE/null phải giữ nguyên trong **cả JSON, CSV ZIP và XLSX**.
- Workflow được nối trigger push main khi Backend/Reader/KIE/contracts/dependency thay đổi, có manual dispatch. Khi #68 chưa merge, cần cập nhật nhánh và chạy PR workflow như lượt này; chưa tuyên bố đã có lịch chạy trên main.

## Kết quả đã chạy lại

| Phép kiểm | Kết quả và bằng chứng |
|---|---|
| Typecheck/lint/build | Đạt trên mã nền mới |
| Unit / browser provider | **58/58 + 30/30 đạt** tại máy và [CI Frontend](https://github.com/vietreceipt-team/vietreceipt/actions/runs/40098707115) |
| Browser provider thật | **4/4 đạt**, [run 40098707182](https://github.com/vietreceipt-team/vietreceipt/actions/runs/40098707182) |
| Worker nguồn mới #70 | 4/4 khớp SHA-256, MIME, số byte với nguồn upload |
| Header/dòng/thuế, 409/reload, verify/export | Đạt; machine snapshots trước/sau không đổi |
| UNREADABLE/null | Đạt trong JSON, CSV ZIP, XLSX; không đổi thành NOT_PRESENT/0/giá trị đoán |
| Ảnh/video trước → sau → kết quả cuối | Đạt; bổ sung khung `06-final-values.png` sau verify hiển thị máy gốc, bản sửa và UNREADABLE cùng lúc |

Đây là lượt chạy **mới sau #69/#70**, không dùng 4/4 ngày 23/10 để suy ra integration mới đã đạt. Lượt đầu trên baseline mới [40098126486](https://github.com/vietreceipt-team/vietreceipt/actions/runs/40098126486) cũng đạt 4/4; bản evidence bàn giao dùng nguyên một lượt hoàn chỉnh 40098707182 sau khi bổ sung khung hình cuối, không ghép mẫu từ nhiều lượt.

PR head lúc quay: `dc2e1a9736c320b6b7b0d1b686acbf1ec52c24d1`; runner/worker checkout merge commit `ffc5f41a5859cd934bdd430811426f4552255cf5`, `git_dirty=false`, Python 3.12.15/Linux x86_64. Provider canonical TV3/TV4 được kiểm tra trực tiếp trong machine attempt. Không đổi baseline grouping để tạo demo và không mở test/final.

[Bộ evidence 24/10](verification/tv6-20261024/README.md) gồm ZIP **79 file**, 4 video, ảnh ba định dạng, ảnh machine/sửa/verified riêng cho challenge, bản reviewed và ba export. [Index](verification/tv6-20261024/index.json) giữ source/run identities và hash từng file; [samples.csv](verification/tv6-20261024/samples.csv) ghi đủ 4 mẫu. [Artifact CI](https://github.com/vietreceipt-team/vietreceipt/actions/runs/40098707182/artifacts/12562140972) còn có service logs. Sau khi tải đã kiểm tra CRC, 79 hashes, source identity, machine snapshot và nội dung các export.

ZIP SHA-256: `6c578b4bc0f5de368d3eb7be27c75f8a7260230aa8332da5f397cbc985a3b9ff`.

Không phát hiện regression trong bốn ca đã chạy; kết luận chỉ áp dụng cho cấu hình và dữ liệu synthetic đã nêu. Mã giao diện sản phẩm không đổi so với bản đã review; phần follow-up là đồng bộ main, kiểm thử/CI và tài liệu/evidence. Các commit tài liệu sau lượt quay không được gán ngược cho runtime.

## Demo và user study

[Kịch bản bảo vệ](tv6-defense-demo.md) chọn bốn file cụ thể, có thứ tự trình diễn, lời dẫn, thao tác sửa/verify/export, 409 tùy chọn, checklist giữ evidence và video dự phòng. [Hướng dẫn chạy lại](tv6-review-demo.md) tiếp tục áp dụng.

TV1 phụ trách chốt thiết kế nghiên cứu. TV6 giữ protocol/worksheet ở trạng thái chuẩn bị; nếu tổ chức pilot sẽ phối hợp đo thời gian, số lần sửa và độ đúng sau review, có consent. Chưa có người tham gia hoặc kết quả user study.
