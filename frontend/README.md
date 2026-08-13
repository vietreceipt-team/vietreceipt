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

Types, mocks, API adapter và tests bám theo canonical `openapi/openapi.yaml` của PR Backend [#3](https://github.com/vietreceipt-team/vietreceipt/pull/3), branch `docs/2-week1-backend-contract`, tại frozen commit `f1eaed210144140184388cdb84d71c1d79493e13` (`f1eaed2`). Snapshot kiểm thử nằm tại `tests/fixtures/backend-contract-v1.3.json`; nếu contract team thay đổi, exact approved SHA, fixture và runtime constants phải được cập nhật cùng một commit Frontend.

- Receipt state: `UPLOADED`, `PROCESSING`, `NEEDS_REVIEW`, `VERIFIED`, `FAILED`; không còn `QUEUED`.
- `POST /api/v1/receipts` trả `UPLOADED` sau khi ảnh và metadata đã commit; enqueue thành công vẫn giữ `UPLOADED`, không có public `/process`.
- `PROCESSING` chỉ bắt đầu khi worker claim/start một processing attempt. Scheduling failure dùng `last_error.stage = SCHEDULING`; `SCHEDULING` không phải processing progress stage.
- Retry `POST /receipts/{receipt_id}/retry` trả `202 RetryAccepted { receipt_id, retry_accepted: true }`, nghĩa là đã nhận để schedule chứ chưa đồng nghĩa receipt đang `PROCESSING`.
- `fields` là object có đúng năm key: `merchant_name`, `receipt_date`, `total_amount`, `invoice_id`, `merchant_address`.
- Backend trả `ExtractedField` dạng phẳng theo OpenAPI; `projectApiExtractedField` chuyển DTO này sang view model `machine/correction/effective` dùng riêng trong UI.
- Correction dùng `PATCH /receipts/{receipt_id}/fields/{field_name}/correction`.
- `APPLY` gửi `value_status`, `value`, `expected_updated_at`; `CLEAR` chỉ gửi `operation` và `expected_updated_at`.
- Public field response và correction `APPLY` dùng canonical type riêng theo `field_name`: amount là integer VND không âm, date là ngày `YYYY-MM-DD` hợp lệ, `invoice_id` luôn là string để giữ leading zero, các field string còn lại không được rỗng; mọi status non-`PRESENT` bắt buộc dùng `null`. Backend trả `422` nếu correction không đúng kiểu/format.
- Verify gửi `expected_updated_at = receipt.updated_at`; stale field/receipt token trả `409`.
- `review_reasons` là mảng string enum KIE v1.1 đúng theo OpenAPI canonical; nhãn tiếng Việt là presentation mapping do Frontend sở hữu.
- `raw_text`, prediction, normalized, correction và effective projection được giữ riêng; effective value không fallback sang prediction chưa chuẩn hóa.

## Evidence ảnh và OCR

Màn hình review dùng ảnh fixture thật `public/fixtures/R001.jpg` từ nhánh OCR `feature/ocr-baseline-week1`, không dựng lại ảnh bằng HTML từ giá trị KIE. Polygon fixture được lấy từ bounding box OCR trên chính fixture 465×564 và liên kết hai chiều với field qua `source_block_ids`.

Đây vẫn là fixture W1. Khi tích hợp thật, `image_url`, `ocr_blocks`, `block_id`, `polygon`, `confidence` và `reading_order` phải đến từ Backend/OCR contract đã được team chốt và có kiểm soát quyền. Frontend chỉ render/interaction, không sở hữu OCR schema, không tự sinh polygon và không suy đoán đường dẫn Storage.

## Tests và bảo mật dependency

`tests/contract-and-interactions.test.ts` kiểm tra runtime constants với contract fixture, flat Backend DTO → UI projection, consistency giữa object key và `field_name`, validation theo từng field, payload `APPLY/CLEAR`, optimistic concurrency `409`, verify và source highlighting hai chiều.

Sau khi chuyển khỏi Vinext beta và nâng các bản vá khả dụng, `npm audit` trả về **0 vulnerabilities** tại thời điểm cập nhật PR #8.
