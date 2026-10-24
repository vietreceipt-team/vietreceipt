# TV6 — chạy lại bằng chứng trình duyệt

Khi chuẩn bị bảo vệ, dùng [kịch bản demo và bộ ví dụ đã chọn](tv6-defense-demo.md). Theo dõi mã nền và lượt kiểm tra sau các PR mới tại [biên bản integration 24/10](tv6-integration-20261024.md).

## Test giao diện với provider kiểm thử

```sh
cd frontend
npm ci
npx playwright install chromium
npm run typecheck
npm test
npm run lint
npm run build
npm run test:e2e
```

Các ảnh nằm ở `frontend/test-results/`. Đây là provider contract/UI tests.

## Backend + Reader + KIE thật

Dùng Python 3.12 và PostgreSQL/Redis riêng theo [hướng dẫn TV5](v2-reproducible-demo.md). Cài `backend/requirements-ai.txt` và `reportlab`, đặt provider canonical, migrate rồi chạy API cổng 18000, worker và beat. Không dùng dữ liệu hóa đơn người dùng hoặc final/test.

```sh
python -m scripts.create_tv6_review_demo --output .data/tv6-demo
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e:real
```

`TV6_BACKEND_URL` đổi origin backend, mặc định `http://127.0.0.1:18000`. `TV6_DEMO_ROOT` đổi đường dẫn manifest (tính từ frontend). Bộ test từ chối dataset không đúng tên/synthetic/demo; SHA-256 được kiểm tra trước upload. Mỗi lần chạy upload receipt mới, không sửa receipt đã tồn tại của người khác.

Workflow `.github/workflows/tv6-real-review.yml` tự tạo stack dịch vụ riêng trên Ubuntu/Python 3.12. File test không có `route.fulfill`/HTTP interception; kiểm tra provider và callable trong machine attempt. Download/model/network failure làm test thất bại, không tự chuyển sang fake provider.

Ba biến thể cơ sở đến từ **một** hóa đơn giả của TV5: JPG, PDF chữ và PDF scan. Một PDF hai trang bổ sung có `Invoice number: 00001234 COPY`, ghi chú COPY là dấu bản sao không thuộc số hóa đơn, và `Invoice symbol: AA/??E` bị che. Reference do tác giả fixture cung cấp, chưa phải gold độc lập. Trường khó đọc giữ UNREADABLE/null thay vì đoán giá trị. Test kiểm tra lỗi PRESENT thực trên challenge trước khi sửa, sửa số về `00001234`, đối chiếu dòng trang 2, rồi verify/export. Không chèn prediction hoặc sửa payload machine để tạo lỗi.

## Artifact

`tv6-real-provider-review` của GitHub Actions chứa:

- Nguồn synthetic/manifest/hash, service logs và báo cáo Playwright.
- Mỗi mẫu: `result.json`, `machine-before.json`, `machine-after.json`, `detail-before.json`, `detail-reviewed.json`, `history.json`, evidence OCR, ảnh từng bước và video.
- `reviewed.json`, `reviewed.zip` (CSV) và `reviewed.xlsx`: kiểm tra nội dung số hóa đơn, không chỉ MIME. Snapshot machine phải giống nguyên vẹn sau sửa/xác nhận/xuất.
- Lỗi giữ `result.json`, machine-failure nếu có, screenshot/trace và service logs. Mẫu lỗi không được loại khỏi kết quả.

`git commit` của runner lấy từ checkout workflow; worker provenance ghi runtime commit/source hash/model/config. Thời gian API/model trong log không phải chỉ số nghiên cứu người dùng. Không gọi bốn file/biến thể này là bốn mẫu độc lập hoặc benchmark final.
