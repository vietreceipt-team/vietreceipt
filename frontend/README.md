# VietReceipt Frontend — Invoice V2

Frontend sản phẩm dùng HTML, CSS và JavaScript thuần (ES modules). Không dùng React, Next.js, Vue, Angular hoặc TypeScript trong runtime. `tsc` chỉ được dùng để kiểm tra JavaScript qua `checkJs`.

## Chạy với backend V2

Yêu cầu Node.js >= 22.13.0. Từ thư mục `frontend/` của repository:

```powershell
npm ci
$env:FRONTEND_DATA_MODE="api"
$env:BACKEND_API_ORIGIN="http://127.0.0.1:8000"
npm run dev
```

Mở `http://127.0.0.1:3000/upload/`. Mặc định frontend ở `api` mode. Server reverse proxy cả `/api/v2/` và `/api/v1/` tới `BACKEND_API_ORIGIN`; trang sản phẩm gọi `/api/v2/`. Nếu backend chưa chạy, giao diện hiện lỗi kết nối, không tạo hóa đơn giả. Không đặt token hoặc secret trong `/runtime-config.js`.

Luồng V2: upload JPEG/PNG/PDF (tối đa 10 MiB) → trạng thái xử lý → danh sách → đối chiếu tài liệu với 13 header, `line_items`, `tax_breakdown` → correction theo từng ô → verify → export JSON, CSV ZIP, XLSX. `CSV` được backend đóng gói thành ZIP ba bảng. Mọi mutation dùng `expected_version`; 409 yêu cầu tải dữ liệu mới. `VERIFIED` chỉ đọc.

PDF nhiều trang được render bằng PDF.js ES modules trong `assets/vendor/`. Evidence từ `/evidence` hỗ trợ OCRResult một trang và `document-2.0` nhiều trang. Source hoặc evidence thiếu sẽ có fallback. Viewer không tạo OCR/KIE; vị trí highlight lấy từ polygon backend trả.

## Kiểm thử

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```

`typecheck` gồm `checkJs` cho API client V2 và source viewer. Playwright dùng HTTP provider giả trong test; nó kiểm chứng giao diện và contract, không chứng minh OCR/KIE thật. Fixture PDF hai trang ở `tests/fixtures/two-page.pdf` là synthetic.

## Pilot V1 cũ

`FRONTEND_DATA_MODE=mock` là chế độ **demo/nghiên cứu V1 được bật tường minh**. Static server phục vụ các module upload/list/review cũ để giữ pilot C1/C2 và E2E lịch sử hoạt động. Chế độ này dùng dữ liệu mock trong `sessionStorage`, chỉ có năm trường receipt cũ và không phải Invoice V2. Không dùng mode này làm bằng chứng tích hợp V2. Trang `/login/` chỉ giải thích rằng backend demo chưa có xác thực production; nó không phải luồng đăng nhập.

Xem [docs/frontend-v2.md](docs/frontend-v2.md) để biết quyết định migration và điểm chờ tích hợp. Contract V2 đối chiếu với `openapi/openapi-v2.yaml` và `backend/app/v2/api.py` trên PR #53.
