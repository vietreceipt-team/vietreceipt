# VietReceipt Frontend — Tuần 1

Giao diện Human-in-the-Loop cho quy trình số hóa hóa đơn tiếng Việt.

- Issue: [#7 — Frontend Task 1](https://github.com/vietreceipt-team/vietreceipt/issues/7)
- Pull Request: [#8](https://github.com/vietreceipt-team/vietreceipt/pull/8)
- Phụ trách: [@phamduyductam-design](https://github.com/phamduyductam-design)
- Phạm vi: chỉ giao tiếp với Backend API; không gọi trực tiếp OCR/KIE, Database hoặc Storage.

## Kiến trúc Frontend

Frontend owner đã xác nhận dùng **Next.js 16.3.0 chính thức** với App Router, React 19.2.8, TypeScript và Tailwind CSS. Vinext beta, Vite và Cloudflare Worker scaffold đã được loại bỏ khỏi module này.

## Màn hình

- `/login`: đăng nhập demo.
- `/upload`: chọn nhiều ảnh JPEG/PNG/WebP tối đa 10 MiB; Backend tự kích hoạt OCR/KIE sau upload.
- `/receipts`: bảng hóa đơn, tìm kiếm, lọc, sắp xếp và phân trang.
- `/receipts/[id]`: đối chiếu ảnh thật với field projection, highlight hai chiều từ `source_block_ids`, chuẩn bị correction `APPLY/CLEAR` và verify.

## Chạy dự án

Yêu cầu Node.js 22.13 trở lên.

```bash
npm ci
npm run dev
```

Mở `http://localhost:3000`. Kiểm tra trước khi tạo Pull Request:

```bash
npm run typecheck
npm run lint
npm test
npm run build
npm audit
```

Không commit project ID, token hoặc thông tin triển khai cá nhân vào repository.

## Contract được pin cho lần đồng bộ này

Types, mocks, API adapter và tests bám theo `openapi/openapi.yaml` trên `docs/2-week1-backend-contract` tại commit `8eb8ee6`. Snapshot kiểm thử nằm tại `tests/fixtures/backend-contract-v1.3.json`; nếu contract team thay đổi, fixture và runtime constants phải được cập nhật cùng một commit.

- Receipt state: `UPLOADED`, `PROCESSING`, `NEEDS_REVIEW`, `VERIFIED`, `FAILED`; không còn `QUEUED`.
- `POST /api/v1/receipts` tự kích hoạt xử lý; không có public `/process`.
- `fields` là object có đúng năm key: `merchant_name`, `receipt_date`, `total_amount`, `invoice_id`, `merchant_address`.
- Correction dùng `PATCH /receipts/{receipt_id}/fields/{field_name}/correction`.
- `APPLY` gửi `value_status`, `value`, `expected_updated_at`; `CLEAR` chỉ gửi `operation` và `expected_updated_at`.
- Verify gửi `expected_updated_at = receipt.updated_at`; stale field/receipt token trả `409`.
- `review_reasons` dùng object `{ code, message? }` và enum KIE v1.1 trong contract.
- `raw_text`, prediction, normalized, correction và effective projection được giữ riêng; effective value không fallback sang prediction chưa chuẩn hóa.

## Evidence ảnh và OCR

Màn hình review dùng ảnh fixture thật `public/fixtures/R001.jpg` từ nhánh OCR `feature/ocr-baseline-week1`, không dựng lại ảnh bằng HTML từ giá trị KIE. Polygon mock được lấy từ bounding box OCR trên chính fixture 465×564 và liên kết hai chiều với field qua `source_block_ids`.

Đây vẫn là fixture W1. Khi tích hợp Backend thật, URL ảnh và OCR blocks phải đến từ endpoint evidence đã được team chốt và có kiểm soát quyền; Frontend không tự suy đoán đường dẫn Storage.

## Tests và bảo mật dependency

`tests/contract-and-interactions.test.ts` kiểm tra runtime constants với contract fixture, canonical fields object, payload `APPLY/CLEAR`, optimistic concurrency `409`, verify và source highlighting hai chiều.

Sau khi chuyển khỏi Vinext beta và nâng các bản vá khả dụng, `npm audit` trả về **0 vulnerabilities** tại thời điểm cập nhật PR #8.
