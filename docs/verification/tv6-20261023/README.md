# Evidence TV6 — 23/10/2026

[Báo cáo](../../tv6-progress-20261023.md) · [Lệnh chạy lại](../../tv6-review-demo.md) · [Run thật](https://github.com/vietreceipt-team/vietreceipt/actions/runs/39968756494).

`browser-evidence.zip` lưu 75 file nguyên byte từ artifact `tv6-real-provider-review`: 4 source/manifest synthetic, machine trước/sau, bản review, evidence OCR, history, screenshot, 4 video và JSON/CSV ZIP/XLSX. Không chứa service logs/model/credentials; logs synthetic của CI nằm trong artifact GitHub riêng.

`index.json` ghi SHA-256 từng file bên trong ZIP, source hashes, receipt/run IDs và commit. `samples.csv` có đủ bốn đầu vào; `metrics.json` ghi 4 pass/0 fail, accuracy=null và 0 người tham gia. Ba biến thể cùng hóa đơn cơ sở và challenge liên quan không phải bốn hóa đơn độc lập.

ZIP SHA-256: `ac02de95a3c4c299bae035f9dd7e1d86fc72155d06e2e600c586cc8e645fcd0d`.

Ảnh `*-review.png` chứng minh trạng thái trước verify, với inspector tách machine/reviewed. Challenge cho thấy lỗi PRESENT `00001234 COPY` được sửa về `00001234` và UNREADABLE giữ null. Ảnh nguồn trang 2 và ảnh verified có trong ZIP. Xem video trong `real-results/browser/*/video.webm`.

`pilot-worksheet.csv` là **worksheet trống**, không phải dữ liệu nghiên cứu. TV1 cần duyệt [protocol](../../tv6-pilot-protocol.md) trước khi tuyển người và đo.
