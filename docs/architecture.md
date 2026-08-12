# Kiến trúc VietReceipt

Backend là orchestration và business-state boundary giữa Frontend, OCR, KIE, Database và private Storage.

```text
Frontend -> Backend -> private Storage
                    -> OCR run -> KIE run -> Backend -> Database
Frontend <- Backend <- effective field projection
```

Frontend không gọi trực tiếp OCR, KIE, Database hay private Storage. OCR/KIE không tự ghi business state vào database chính.

## Sources of truth

- Backend public API: [`../openapi/openapi.yaml`](../openapi/openapi.yaml).
- OCR result: [`../schemas/ocr-result.schema.json`](../schemas/ocr-result.schema.json).
- KIE result: [`../schemas/kie-result.schema.json`](../schemas/kie-result.schema.json).
- Cross-module semantics: [`integration-contracts.md`](integration-contracts.md).

Tài liệu kiến trúc không định nghĩa lại JSON shape để tránh contract drift.

## Processing flow

```text
Authenticated upload
  -> validate MIME/content/size
  -> store private image object
  -> create owned receipt: UPLOADED
  -> Backend automatically triggers processing: PROCESSING
  -> persist immutable OCR run
  -> run KIE against that OCR run
  -> persist immutable KIE run and machine fields
  -> NEEDS_REVIEW
  -> human correction/review
  -> VERIFIED
```

Frontend không cần và không được yêu cầu gọi endpoint `/process`. Processing failure chuyển receipt sang `FAILED`; Backend retry tạo run IDs mới và không overwrite run cũ.

## Data ownership

- OCR sở hữu immutable OCR text, geometry, confidence và reading order.
- KIE sở hữu immutable machine prediction, normalization, value status, review state và provenance theo từng KIE run.
- Backend/Human sở hữu corrections và append-only correction history.
- Backend dẫn xuất effective status/value/review state; không fallback effective value sang predicted value.
- Database là source of truth cho receipt lifecycle, ownership, run linkage, correction audit và verification audit.
- Storage chỉ giữ private image object; local path không phải cross-service contract.

## Security and consistency boundaries

Mọi receipt endpoint yêu cầu authentication và ownership. Correction/verification lưu actor cùng timestamp có timezone. Các mutation dùng optimistic concurrency; stale update trả HTTP `409`.

Backend validate schema tại module boundaries, enforce canonical field types, source-run integrity, uniqueness, immutable runs và verification invariants trong transaction/domain service chung.

Receipt response phản ánh đúng processing stage: trước khi KIE hoàn tất (`UPLOADED`, `PROCESSING`, `FAILED`) không bắt buộc có field projection; từ `NEEDS_REVIEW` trở đi phải có đúng năm canonical fields. Field corrections dùng `field.updated_at`; receipt verification dùng `receipt.updated_at` làm optimistic-concurrency token.

## Lifecycle

```text
UPLOADED -> PROCESSING -> NEEDS_REVIEW -> VERIFIED
                       \-> FAILED
FAILED -> PROCESSING (Backend retry)
```

Chỉ receipt đã giải quyết đủ năm canonical fields mới được verify. Chỉ `VERIFIED` được dùng mặc định cho official export và spending totals.
