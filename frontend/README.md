# VietReceipt Frontend — HTML/CSS/JavaScript thuần

Frontend Human-in-the-Loop của VietReceipt được chuyển từ Next.js/React/TypeScript sang HTML, CSS và JavaScript ES modules. Việc đổi runtime không thay đổi product contract W1/W2: upload → processing → review → APPLY/CLEAR correction → verify, cùng FAILED/retry.

Frontend giữ các yêu cầu W1/W2 và bổ sung pilot research-safe W3 Issue #27 cho C1 manual và C2 verify-all. C3 selective review không được triển khai hoặc bật.

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
FRONTEND_STUDY_MODE=C1_MANUAL
FRONTEND_STUDY_ORDER=C1_MANUAL,C2_VERIFY_ALL
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

Payload event không chứa ảnh, OCR text, field value, phím đã gõ, token hoặc credential. Summary chỉ có processing/waiting time, active review time (đã loại trừ thời gian chờ API), confirmation count, correction count thực sự làm đổi giá trị/trạng thái, keystroke count và completion timestamp. Frontend không auto-verify, không selective-skip và không tuyên bố tiết kiệm thời gian khi chưa chạy study.

## W3 pilot modes

- `C1_MANUAL`: form trống đủ năm canonical fields; DOM không render prediction, confidence, review reason, OCR text hoặc evidence overlay.
- `C2_VERIFY_ALL`: hiển thị prediction/evidence nhưng cả năm field khởi tạo ở trạng thái cần xác nhận; confidence không được dùng để skip.
- `FRONTEND_STUDY_ORDER` phải là một permutation của C1/C2 và bắt đầu bằng `FRONTEND_STUDY_MODE`; đổi thứ tự để counterbalance hai nhóm.
- Nút **Reset phiên nghiên cứu** xóa tiến trình condition trong `sessionStorage`; không lưu field data hoặc participant identifier.
- Sau verify, session chuyển sang condition kế tiếp trong order cho receipt tiếp theo.
- Unit/integration dry-run dùng dữ liệu synthetic; Playwright browser E2E render và thao tác DOM thật cho C1 no-leak, C2 five-field verify, keyboard, stale 409 và retryable failure.
- Không có C3 selective review và không có claim về hiệu quả thời gian.

## Cấu trúc

```text
assets/
  css/                 stylesheet đã biên dịch + app overrides
  fonts/               Geist/Geist Mono Latin và tiếng Việt
  js/
    api.js              Backend DTO validation + mock/HTTP boundary
    review-state.js     per-field state và reconcile logic
    review-workflow.js  mutation/refresh outcome tách biệt
    review-telemetry.js privacy-safe timing/count measurement hooks
    study-mode.js       C1/C2 state, renderer, counterbalancing session
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
