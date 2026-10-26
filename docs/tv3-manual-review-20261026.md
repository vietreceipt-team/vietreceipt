# TV3 — ghi nhận đối chiếu thủ công, cập nhật 26/10/2026

Thành viên TV3 đã báo hoàn tất việc xem và đối chiếu 14 mã mẫu trong gói TV2
PR #66. Kết luận do người dùng xác nhận trong trao đổi ngày 24/10/2026:
**chưa phát hiện lỗi trong phạm vi các mẫu đã xem**; phần lớn mẫu có bố cục
tương tự, ảnh rõ hoặc chỉ mờ nhẹ. Đây là ghi nhận quan sát thủ công, không phải
accuracy bằng 100% hoặc xác nhận mọi biến thể và evidence run đều đúng.

## Phạm vi mẫu

Định danh dưới đây có tiền tố `VRSYN2-`. Split và layout được đối chiếu với
registry TV2 tại commit `89281198ebaf419e511b4c99321ca3355e94fcf1`.

| Mã mẫu | Split | Layout |
| --- | --- | --- |
| 00001 | train | corporate |
| 00002 | train | retail |
| 00003 | train | service |
| 00004 | validation | table_heavy |
| 00009 | train | service |
| 00010 | validation | table_heavy |
| 00015 | train | service |
| 00016 | validation | table_heavy |
| 00021 | train | service |
| 00022 | validation | table_heavy |
| 00025 | train | corporate |
| 00026 | train | retail |
| 00027 | train | service |
| 00028 | validation | table_heavy |

Tổng cộng **14 mã mẫu: 9 train + 5 validation**, thuộc 4 nhóm layout:
corporate (2), retail (2), service (5), table_heavy (5). Các mã mẫu không đồng
nghĩa với số file/biến thể đã review. Người dùng chưa chỉ rõ từng variant,
receipt/ocr_run ID hoặc từng vùng/block đã kiểm, nên chưa quy đổi thành 56
file hay toàn bộ 80 bản ghi của gói handoff.

Nguồn đối chiếu phiên bản:
[base registry](https://github.com/vietreceipt-team/vietreceipt/blob/89281198ebaf419e511b4c99321ca3355e94fcf1/data/manifests/synthetic_v0.2.0/base.csv),
[gói nguồn/gold/evidence TV2](https://github.com/vietreceipt-team/vietreceipt/blob/89281198ebaf419e511b4c99321ca3355e94fcf1/data/handoffs/tv4-dev-v1.zip).
Các liên kết này ghi nhận bối cảnh dữ liệu, chưa thay thế phiếu review gắn với
đúng hash artifact. Phiếu source gold/regions/rows và block alignment chưa
được điền từ thông tin thiếu; trạng thái QA/protocol vẫn giữ pending.

## Phân biệt source gold và transcript OCR

Người dùng nhận thấy dòng cuối trang “DỮ LIỆU GIẢ LẬP - KHÔNG CÓ GIÁ TRỊ
THANH TOÁN” không có trong `source-gold.json`. Source gold KIE chỉ gán nhãn
13 canonical header fields và 5 ô mỗi dòng hàng, nên dòng chú thích này nằm
ngoài phạm vi nhãn đó. Đây không phải một field KIE bị bỏ sót.

Transcript dùng để đo OCR chứa toàn bộ visible text. Kiểm tra artifact đã lưu
xác nhận cả 5 transcript validation `00004`, `00010`, `00016`, `00022`, `00028`
đều có dòng chú thích trên; evidence PDF text của mẫu `00004` cũng giữ nó ở
block `p0_b000030`. Kiểm tra này không suy ra toàn bộ transcript của 14 mã đã
được người dùng review. Khi kiểm OCR thiếu/sai chữ, đối chiếu ảnh với full
transcript và OCR evidence; khi kiểm KIE gold, đối chiếu các field/ô được gán
nhãn với nguồn.

## Liên hệ với thí nghiệm đã bàn giao

Danh sách 14 mã được xem thủ công tách với cohort thí nghiệm PR #65: 20 file
validation từ 5 base `table_heavy`, mỗi base có text PDF, PNG sạch, PDF scan và
PNG mờ. Hai mode OCR-all/route-aware có 40 lượt đọc thật, đủ evidence, hash,
metadata, route/fallback, stage latency, CER/WER và ví dụ lỗi. 40/40 lượt qua
contract checks và source-frame audit; đây là kiểm tra kỹ thuật.

[Báo cáo và lệnh chạy lại](tv3-tv2-v02-20261024.md) giữ nguyên số liệu và
provenance của lượt đã đo. Commit kỹ thuật `3ea5c99` đã có 5/5 CI checks đạt.
Đợt cập nhật này chỉ bổ sung báo cáo thủ công, không chạy lại hoặc thay đổi
prediction, gold, cohort, metrics hay cấu hình Reader.

Quan sát “chưa phát hiện lỗi” của người dùng không xóa các sai khác OCR đã lưu
trong báo cáo kỹ thuật. KIE baseline `invoice-baseline/2.1.0` vẫn có
`line_items=[]` trong 40 machine results dù nguồn có bảng hàng hóa; đây là
quan sát artifact cần TV4 điều tra, không phải lỗi mới do người dùng báo.

## Việc cần phối hợp

- TV2 cùng reviewer ghi rõ từng input/variant, người tạo nhãn/người review,
  thời điểm thực tế, source/gold/region hashes, phần đã duyệt và unresolved
  trong phiếu chính thức; duyệt mapping riêng cho mỗi evidence run/mode.
- TV4 kiểm tra đầu ra bảng hàng hóa, xác nhận evaluator/matcher/config và chấm
  13 trường + bảng sau khi gold/alignment đủ điều kiện. Tax groups nằm ngoài
  scope complete-invoice hiện tại.
- Bộ mẫu synthetic có layout lặp và mức suy giảm nhẹ; chưa suy ra chất lượng
  trên hóa đơn thực tế hoặc ảnh mờ/nhiễu nặng. Kết quả vẫn là development
  experiment. Final test tiếp tục khóa và issue #48 giữ mở cho các gate còn lại.

[Quy trình bàn giao reviewed gold](tv3-tv4-reviewed-gold-handoff.md) ·
[Coordinate contract](tv3-coordinate-handoff.md) ·
[PR #65](https://github.com/vietreceipt-team/vietreceipt/pull/65).
