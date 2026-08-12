# Contract v1 Review and Sign-off

Each owner must answer every item with **Yes**, or open a linked Issue describing the required change. Silence is not approval.

## Frontend owner

- [ ] I know how to upload an image and which MIME types/size are allowed.
- [ ] I know how to start processing and poll receipt status.
- [ ] I can render OCR polygons using normalized coordinates and returned image dimensions.
- [ ] I know the canonical type of all five fields.
- [ ] I understand `value_status`, `has_correction`, `effective_value`, `effective_status`, `machine_needs_review` and `effective_needs_review`.
- [ ] I use `effective_needs_review`, not the immutable machine flag, for current warning indicators.
- [ ] I know how to edit a field, verify a receipt and display API errors.
- [ ] I do not need to call OCR, KIE, database or storage directly.

## Backend owner

- [ ] Every endpoint has a request, response, error and allowed-state definition.
- [ ] Every status transition is implemented in one domain service.
- [ ] Processing requests and retries are idempotent.
- [ ] Authorization scopes every receipt by the current user.
- [ ] Raw, predicted, normalized, corrected and effective value layers remain distinct.
- [ ] OCR/KIE outputs are append-only by `ocr_run_id` and `kie_run_id`.
- [ ] A user can confirm `NOT_PRESENT` without that action being treated as clearing a correction.
- [ ] `effective_value` never falls back to `predicted_value`.
- [ ] I derive `effective_needs_review` after correction and verification.
- [ ] Only verified receipts are exported by default.

## OCR owner

- [ ] I accept `receipt_id` and a local image path from the worker.
- [ ] I return `schema_version`, `ocr_run_id`, engine metadata, image dimensions and blocks.
- [ ] Every block has text, confidence, a four-point normalized polygon and reading order.
- [ ] Polygon point order and coordinate origin match the shared convention.
- [ ] I return an empty block list for no detections and a typed error for engine failure.
- [ ] I do not write directly to Backend's database.

## KIE owner

- [ ] I accept the engine-independent OCR result schema.
- [ ] I always return `merchant_name`, `receipt_date`, `total_amount`, `invoice_id` and `merchant_address`.
- [ ] I return `kie_run_id` and the exact `source_ocr_run_id`.
- [ ] I keep `raw_text`, `predicted_value` and `normalized_value` distinct.
- [ ] My normalized types are string/date/integer as specified.
- [ ] I return an explicit `value_status` and do not invent missing values.
- [ ] Every entry in `source_block_ids` exists in the referenced OCR run.
- [ ] Ambiguous normalization returns `normalized_value=null` and `machine_needs_review=true`.
- [ ] Field confidence means confidence in the normalized business value.
- [ ] Ground-truth annotation records use the separate annotation schema and are not emitted as KIE runtime output.
- [ ] Annotation `field_name`, status, typed values and `source_block_ids` match the five-field specification.

## DevOps owner

- [ ] I know which components are deployed: API, worker, PostgreSQL, Redis and MinIO/S3.
- [ ] I know which service owns durable data and which service only transports jobs.
- [ ] I can configure secrets without committing them.
- [ ] API and worker use the same contract/package version.
- [ ] Private object storage and log redaction are enforced.
- [ ] Health checks and worker/queue visibility are defined for deployment.

## Final unresolved decisions

Complete before merge:

| Decision | Proposed v1 | Owner | Accepted/change |
| --- | --- | --- | --- |
| OCR polygon available | Four normalized points | OCR | Pending |
| OCR reading order | Unique, zero-based | OCR | Pending |
| Raw field property | `raw_text` | KIE + Backend | Accepted by KIE |
| OCR source reference | `source_block_ids` array | OCR + KIE | Accepted by KIE; OCR sign-off pending |
| Value layers | raw / predicted / normalized / corrected / effective | KIE + Backend | Accepted by KIE; v1.3 review semantics pending |
| Review flags | Immutable `machine_needs_review`; Backend-derived `effective_needs_review` | KIE + Backend + Frontend | Added in v1.3; re-review pending |
| Value status | PRESENT / NOT_PRESENT / UNREADABLE / AMBIGUOUS / UNKNOWN | KIE + Backend | Accepted by KIE |
| Canonical field names | merchant_name / receipt_date / total_amount / invoice_id / merchant_address | All | Accepted by KIE; other owners pending |
| Run preservation | Immutable `ocr_run_id` and `kie_run_id` | OCR + KIE + Backend | Accepted by KIE |
| Total canonical type | Integer VND | KIE + Backend | Accepted by KIE |
| Date canonical type | ISO `YYYY-MM-DD` | KIE + Backend | Accepted by KIE |
| Queue implementation | Redis/Celery | Backend + DevOps | Pending |
| Upload maximum | 10 MiB | Backend + Frontend | Pending |
| Allowed formats | JPEG, PNG, WebP | Backend + Frontend | Pending |
| Confidence thresholds | Configurable/TBD until calibration | KIE + Backend | Accepted as provisional by KIE |

## Sign-off

| Role | GitHub username | Date | Result |
| --- | --- | --- | --- |
| Frontend |  |  | Pending |
| Backend |  |  | Pending |
| OCR |  |  | Pending |
| KIE | minh-phuong0104 | 2026-08-11 | Main blockers resolved; v1.3 review-flag clarification pending |
| DevOps/Lead |  |  | Pending |
