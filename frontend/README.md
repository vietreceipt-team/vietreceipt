# VietReceipt Frontend — HTML/CSS/JavaScript thuần

Frontend Human-in-the-Loop của VietReceipt được chuyển từ Next.js/React/TypeScript sang HTML, CSS và JavaScript ES modules. Việc đổi runtime không thay đổi product contract W1/W2: upload → processing → review → APPLY/CLEAR correction → verify, cùng FAILED/retry.

Phạm vi này giữ toàn bộ yêu cầu đã chốt ở Frontend W1 Issue #7 và W2 Issue #13. Không bao gồm pilot mode hoặc yêu cầu W3.

## Chạy local

Yêu cầu Node.js 22.13 trở lên:

```powershell
npm ci
npm run dev
```

Mở `http://127.0.0.1:3000`. Các route được giữ nguyên:

- `/login/`
- `/upload/`
- `/receipts/`
- `/receipts/{receipt_id}/`

## Validation

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npm audit --audit-level=high
```

`typecheck` dùng TypeScript `checkJs`/JSDoc để kiểm tra kiểu thật cho API boundary, review state/workflow và runtime server; source vẫn chỉ là JavaScript. `lint` kiểm tra syntax toàn bộ ES modules, xác nhận không còn `.ts/.tsx`, enforcement rằng UI modules không gọi `fetch()` ngoài API boundary và telemetry không chứa dữ liệu nhạy cảm.

## Mock và Backend thật

Local mặc định chạy `dataMode: "mock"`. Mock HTTP adapter dùng cùng interface với API thật và lưu fixture trong `sessionStorage`, nên upload thành công vẫn điều hướng được sang `/receipts/{receipt_id}/`.

Không cần sửa source để bật Backend thật. Server sinh `/runtime-config.js`; đặt các biến lúc khởi động:

```dotenv
FRONTEND_DATA_MODE=api
BACKEND_API_ORIGIN=http://localhost:8000
```

Giữ API base cùng origin để browser gọi `/api/v1`; server reverse proxy tới `BACKEND_API_ORIGIN`. Docker Compose mặc định đặt `FRONTEND_DATA_MODE=api` và `BACKEND_API_ORIGIN=http://backend:8000`, vì vậy container dùng Backend thật qua internal network. Không đặt token, mật khẩu hoặc secret trong runtime config public.

## W1/W2 workflow được giữ

- Public states: `UPLOADED`, `PROCESSING`, `NEEDS_REVIEW`, `VERIFIED`, `FAILED`; không public `QUEUED`.
- Upload dùng multipart field `file`, không gọi `/process`, và điều hướng tới detail sau success.
- Detail polling 2,5 giây, bounded backoff tối đa 10 giây/120 lần, cleanup khi rời trang, dừng ở terminal states.
- Processing stage chỉ render `PREPROCESSING`, `OCR`, `KIE`, `PERSISTING`; không tự bịa phần trăm.
- Năm canonical fields luôn được giữ: `merchant_name`, `receipt_date`, `total_amount`, `invoice_id`, `merchant_address`.
- Mỗi field có `VIEW`, `EDITING`, `SAVING`, `SAVE_ERROR`, `STALE`, `SAVED`.
- `APPLY` và `CLEAR` dùng `field.updated_at`; correction response là authoritative field.
- Sau correction, GET detail lấy `receipt.updated_at` mới nhưng giữ draft chưa lưu của field khác.
- HTTP 409 không auto-retry; UI hiện nút **Tải phiên bản mới**.
- Verify dùng `receipt.updated_at`; chỉ Backend quyết định kết quả cuối.
- VERIFIED là read-only và vẫn hiển thị machine, human correction, effective value cùng OCR evidence.
- FAILED chỉ hiện retry khi `retryable=true`; HTTP 202 chỉ nghĩa schedule đã được chấp nhận.
- Field → nhiều OCR blocks và OCR block → nhiều fields đều được highlight; source block thiếu làm adapter fail projection.
- Keyboard: `Ctrl/⌘+Enter` lưu APPLY, `Esc` bỏ draft, `Alt+↑/↓` chuyển field.

## Telemetry measurement-ready

`assets/js/review-telemetry.js` phát event `vietreceipt:review-event` cho:

- review bắt đầu từ tương tác pointer/focus/keyboard đầu tiên, không phải lúc render;
- focus/edit field;
- APPLY/CLEAR correction;
- verify, chuyển receipt và retry.

Payload chỉ có event name, timestamp, receipt ID, field/operation khi cần và `PREFILL_FULL_REVIEW`. Không chứa ảnh, OCR text, field value, token hoặc credential. Frontend không auto-verify, không selective-skip và không claim confidence đã calibration.

## Cấu trúc

```text
assets/
  css/                 stylesheet đã biên dịch + app overrides
  fonts/               Geist/Geist Mono Latin và tiếng Việt
  js/
    api.js              Backend DTO validation + mock/HTTP boundary
    review-state.js     per-field state và reconcile logic
    review-workflow.js  mutation/refresh outcome tách biệt
    review-telemetry.js privacy-safe measurement hooks
    common.js           navigation/constants/formatters
    config.js           mock/API configuration
    mock-data.js        canonical W1/W2 fixtures
    login.js
    upload.js
    receipts.js
    receipt-detail.js
login/index.html
upload/index.html
receipts/index.html
receipts/detail.html
scripts/               typecheck/lint/build
tests/                 contract + workflow + interaction tests
server.js               static routes + runtime config + Backend reverse proxy
```

Mọi network request nằm trong `assets/js/api.js`; UI modules chỉ gọi `vietReceiptApi`. Frontend không gọi OCR/KIE, database hoặc storage trực tiếp và không tự tạo polygon.
