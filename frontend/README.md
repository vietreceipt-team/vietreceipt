# VietReceipt Frontend — Tuần 1

Bộ khung giao diện Human-in-the-Loop cho quy trình số hóa hóa đơn tiếng Việt. Dự án dùng Next.js App Router, TypeScript, Tailwind CSS và dữ liệu mẫu cục bộ.

- Issue: [#7 — Frontend Task 1](https://github.com/vietreceipt-team/vietreceipt/issues/7)
- Phụ trách: [@phamduyductam-design](https://github.com/phamduyductam-design)
- Phạm vi: chỉ giao tiếp với Backend API; không gọi trực tiếp OCR/KIE, Database hoặc Storage.

## Màn hình

- `/login`: đăng nhập demo.
- `/upload`: kéo thả/chọn nhiều ảnh JPEG/PNG/WebP tối đa 10 MiB, theo dõi tiến độ tải mô phỏng.
- `/receipts`: bảng hóa đơn, tìm kiếm, lọc, sắp xếp, phân trang và xử lý trạng thái lỗi.
- `/receipts/[id]`: đối chiếu ảnh–dữ liệu dạng split screen, zoom/xoay, sửa 5 trường cốt lõi và xác minh.

## Chạy dự án

Yêu cầu Node.js 22.13 trở lên.

```bash
npm install
npm run dev
```

Mở `http://localhost:3000`. Kiểm tra bản phát hành bằng:

```bash
npm run build
npm run typecheck
npm run lint
npm test
```

Không commit project ID, token hoặc thông tin triển khai cá nhân vào repository.

## Cấu trúc chính

```text
app/
  login/page.tsx
  upload/page.tsx
  receipts/page.tsx
  receipts/[id]/page.tsx
  layout.tsx
  globals.css
components/
  navigation.tsx
  receipt-thumbnail.tsx
  status-badge.tsx
data/
  mock-receipts.ts
types/
  receipt.ts
```

## Hợp đồng dữ liệu

Mock data và TypeScript types bám theo OpenAPI draft v1.3 trên nhánh `docs/2-week1-backend-contract` và các quyết định KIE mới nhất trên `docs/1-kie-field-spec`.

- Năm field canonical: `merchant_name`, `receipt_date`, `total_amount`, `invoice_id`, `merchant_address`.
- `receipt_date` dùng `YYYY-MM-DD`; `total_amount` là integer VND; `invoice_id` luôn là string để giữ số 0 đầu.
- State machine: `UPLOADED`, `QUEUED`, `PROCESSING`, `NEEDS_REVIEW`, `VERIFIED`, `FAILED`.
- Value status: `PRESENT`, `NOT_PRESENT`, `UNREADABLE`, `AMBIGUOUS`, `UNKNOWN`.
- Các lớp `raw_text`, `predicted_value`, `normalized_value`, `corrected_value` và `effective_value` được giữ riêng. `effective_value` không fallback sang prediction chưa chuẩn hóa.
- Frontend dùng `effective_needs_review` cho cảnh báo hiện tại; `machine_needs_review` chỉ là bằng chứng bất biến từ KIE. `LOW_CONFIDENCE` là review reason, không phải value status.
- Dữ liệu thiếu dùng JSON `null`, không dùng chuỗi rỗng, số 0 giả hoặc nhãn “không xác định”.

Luồng API v1.3 dùng `/api/v1`: upload tạo `UPLOADED`, sau đó gọi endpoint `/process`; danh sách chỉ tiêu thụ `ReceiptSummary`, còn màn hình review dùng `ReceiptDetail` và `ExtractedField`. Ảnh được lấy qua endpoint Backend có kiểm soát quyền, không truy cập Storage trực tiếp.

Tuần 1 vẫn dùng mock data và tương tác phía trình duyệt; chưa gửi thông tin đăng nhập, ảnh hay correction tới Backend thật.
