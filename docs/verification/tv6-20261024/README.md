# TV6 — evidence integration/demo sau #69/#70, ngày 24/10/2026

[Biên bản integration](../../tv6-integration-20261024.md) · [Kịch bản bảo vệ](../../tv6-defense-demo.md) · [CI thật](https://github.com/vietreceipt-team/vietreceipt/actions/runs/40098707182) · [Artifact CI](https://github.com/vietreceipt-team/vietreceipt/actions/runs/40098707182/artifacts/12562140972).

Mã nền main: `07c7cd00b0a12a555ec98f1ba45c7d1f1584e5eb` (Backend #70 + KIE #69 đã merge). PR head `dc2e1a9`; runner/worker merge commit `ffc5f41a5859cd934bdd430811426f4552255cf5`, dirty=false. Reader #65 và follow-up #71 còn mở lúc kiểm tra; không lấy các nhánh này vào evidence.

## Bộ ví dụ bảo vệ

| Ví dụ | Ảnh review | Nguồn/video đầy đủ |
|---|---|---|
| JPG | [jpg-review.png](jpg-review.png) | `inputs/photo.jpg`, `real-results/browser/review-jpg-*/video.webm` trong ZIP |
| PDF chữ | [text_pdf-review.png](text_pdf-review.png) | `inputs/text.pdf`, video case `text-pdf` trong ZIP |
| PDF scan | [scan_pdf-review.png](scan_pdf-review.png) | `inputs/scan.pdf`, video case `scan-pdf` trong ZIP |
| AI sai, hai trang | [Video trình diễn](challenge-demo.webm) | `inputs/challenge.pdf`, 12 dòng trên trang 2 |

## Ba trạng thái cần cho thấy trong demo

1. [Trước sửa](challenge-machine.png): `00001234 COPY` là machine PRESENT; ký hiệu là machine UNREADABLE/trống.
2. [Sau sửa](challenge-reviewed.png): inspector phân biệt máy `00001234 COPY` với người sửa `00001234`; [dòng hàng/source trang 2](challenge-source-row.png).
3. [Sau verify/export](challenge-verified.png): nhãn Đã xác nhận, số đã sửa, machine gốc trong inspector và UNREADABLE/trống cùng khung hình. [Ảnh verified của dòng hàng và menu export](challenge-lines-verified.png) là góc nhìn bổ sung.

UNREADABLE vẫn null trong JSON, ô rỗng + trạng thái UNREADABLE trong CSV và XLSX. Đây là đối chiếu trạng thái không đọc được, không phục hồi ký tự đã che.

## Tái kiểm chứng

[browser-evidence.zip](browser-evidence.zip) chứa **79 file nguyên byte**: 4 nguồn synthetic/manifest, machine-before/after, detail-before/reviewed, history, OCR evidence, ảnh từng bước, 4 video và JSON/CSV ZIP/XLSX. [index.json](index.json) ghi SHA-256 từng file cùng receipt/OCR/KIE run IDs; [samples.csv](samples.csv) giữ đủ 4 mẫu với worker input hash khớp nguồn. ZIP CRC và mọi hash đã kiểm tra sau khi tải từ CI; service logs chỉ lưu trong artifact CI, không thêm vào Git ZIP.

ZIP SHA-256: `6c578b4bc0f5de368d3eb7be27c75f8a7260230aa8332da5f397cbc985a3b9ff`.

Không thay [bằng chứng 23/10](../tv6-20261023/README.md). Các mẫu liên quan cùng hóa đơn giả/template; accuracy=null và 0 người tham gia. Video là browser tự động, không phải dữ liệu user study. TV1 chốt thiết kế nghiên cứu; TV6 phối hợp pilot khi được tổ chức và có consent.
