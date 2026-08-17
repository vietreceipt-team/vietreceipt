# VietReceipt Frontend — W2 receipt workflow

Next.js App Router frontend cho workflow Human-in-the-Loop của VietReceipt:

```text
Upload → UPLOADED/PROCESSING → NEEDS_REVIEW → APPLY/CLEAR → VERIFIED
                                      └──── FAILED → Retry ────┘
```

- W2 issue: [#13](https://github.com/vietreceipt-team/vietreceipt/issues/13)
- Frontend owner: [@phamduyductam-design](https://github.com/phamduyductam-design)
- Frontend chỉ gọi canonical FastAPI REST API; không gọi OCR/KIE, Database, Storage hay tự sinh polygon.

## Chạy dự án

Yêu cầu Node.js 22.13 trở lên.

```bash
npm ci
npm run dev
```

Mặc định trình duyệt gọi cùng origin tại `/api/v1`. Khi phát triển local, cấu hình server-side rewrite để tránh CORS:

```dotenv
BACKEND_API_ORIGIN=http://localhost:8000
```

Nếu Backend được expose trực tiếp cho trình duyệt và đã cấu hình CORS/cookie phù hợp, có thể dùng:

```dotenv
NEXT_PUBLIC_VIETRECEIPT_API_BASE_URL=http://localhost:8000
```

Biến public chỉ chứa origin, không chứa credential hay token. `frontend/lib/vietreceipt-api.ts` là integration boundary duy nhất; React components không gọi `fetch()` trực tiếp.

## API dependency

W2 sử dụng các endpoint đã merge trong Backend PR [#19](https://github.com/vietreceipt-team/vietreceipt/pull/19):

- `POST /api/v1/receipts`
- `GET /api/v1/receipts`
- `GET /api/v1/receipts/{receipt_id}`
- `PATCH /api/v1/receipts/{receipt_id}/fields/{field_name}/correction`
- `POST /api/v1/receipts/{receipt_id}/verify`
- `POST /api/v1/receipts/{receipt_id}/retry`

Exact integration pin:

- Backend PR #19 head: `2793a6b93b97506b0b38c63168fa0e953c965f54`
- Merge commit trên `main`: `7b1a40eef791af81f320fdc47fdf1393ae822ddf`
- Frozen shared OpenAPI v1.3 vẫn bắt nguồn từ PR #3 commit `f1eaed210144140184388cdb84d71c1d79493e13`.

Pin kiểm thử nằm tại `tests/fixtures/backend-contract-v1.3.json`. Khi contract thay đổi, cần cập nhật exact approved SHA, adapter, fixture và contract tests cùng một commit; không copy một fixture mới rồi để test xanh độc lập với canonical OpenAPI.

## Trạng thái và polling

Frontend render đúng năm public states: `UPLOADED`, `PROCESSING`, `NEEDS_REVIEW`, `VERIFIED`, `FAILED`.

- Polling chỉ chạy trong `UPLOADED` và `PROCESSING`.
- Interval đầu là 2,5 giây, backoff có giới hạn 10 giây và tối đa 120 lần.
- Polling dừng khi sang `NEEDS_REVIEW`, `VERIFIED`, `FAILED`, khi component unmount hoặc khi receipt ID đổi.
- Chỉ hiển thị `PREPROCESSING/OCR/KIE/PERSISTING` do Backend trả; không tự tạo phần trăm tiến độ.
- Retry `202` chỉ có nghĩa Backend đã chấp nhận schedule. UI tải lại receipt thay vì tự gán `PROCESSING`.

## Correction, stale write và authority

Mỗi canonical field có state riêng: `VIEW`, `EDITING`, `SAVING`, `SAVE_ERROR`, `STALE`, `SAVED`.

- `APPLY` dùng `field.updated_at`; `CLEAR` không gửi `value` hoặc `value_status`.
- Response correction thay đúng field local trước tiên.
- Backend correction đồng thời làm đổi `receipt.updated_at` nhưng response chỉ chứa field, nên UI gọi lại `GET receipt` để lấy token verify mới. Frontend không tự suy ra timestamp hay effective value.
- Khi nhận `409`, UI không retry mutation. Nó khóa hành động liên quan và yêu cầu người dùng bấm **Tải phiên bản mới**.
- Verify dùng `receipt.updated_at` và Backend là authority cuối cùng.
- `VERIFIED` là read-only nhưng vẫn giữ machine value, human correction, effective value và OCR evidence.

## Evidence và HITL

Backend trả `image_url`, `ocr_blocks` và `source_block_ids`. Frontend:

- render đúng polygon bốn điểm;
- field → highlight toàn bộ source blocks;
- polygon → focus field liên quan;
- fail projection nếu một `source_block_id` không tồn tại, vì tiếp tục render sẽ trình bày provenance sai;
- không generate/guess polygon, không reconstruct ảnh và không fallback effective value sang predicted value.

Warning hiện tại dùng `effective_needs_review`. Confidence và `machine_needs_review` chỉ là provenance/presentation; W2 không auto-verify, không ẩn field confidence cao và không selective-skip khi chưa có calibrated evidence.

Keyboard cơ bản:

- `Ctrl/⌘ + Enter`: lưu APPLY cho field;
- `Esc`: bỏ draft local;
- `Alt + ↑/↓`: chuyển field.

## Measurement-ready telemetry

`frontend/lib/review-telemetry.ts` phát event hook `vietreceipt:review-event` cho review start, field focus/edit, APPLY, CLEAR, verify, chuyển receipt và retry. `REVIEW_STARTED` chỉ phát ở tương tác pointer/focus/keyboard đầu tiên của người review; render màn hình không tự tính là bắt đầu review. Payload chỉ gồm event name, timestamp, receipt ID, field/operation khi cần và `PREFILL_FULL_REVIEW` mode.

Không log raw image bytes, OCR text, field value, token hoặc credential. Task này không gửi telemetry tới analytics backend và không claim selective review hiệu quả.

## Kiểm tra trước Pull Request

```bash
npm run typecheck
npm run lint
npm test
npm run build
npm audit --audit-level=high
```

Root contract suite vẫn phải chạy để phát hiện drift với shared OpenAPI:

```bash
python tests/contracts/run_contract_tests.py
```
