# Contract v1 Review and Sign-off

Each owner must answer every item with **Yes**, or open a linked Issue describing the required change. Silence is not approval.

## Frontend owner

- [ ] I know how to upload an image and which MIME types/size are allowed.
- [ ] I know how to start processing and poll receipt status.
- [ ] I can render OCR polygons using normalized coordinates and returned image dimensions.
- [ ] I know the canonical type of all five fields.
- [ ] I know how to edit a field, verify a receipt and display API errors.
- [ ] I do not need to call OCR, KIE, database or storage directly.

## Backend owner

- [ ] Every endpoint has a request, response, error and allowed-state definition.
- [ ] Every status transition is implemented in one domain service.
- [ ] Processing requests and retries are idempotent.
- [ ] Authorization scopes every receipt by the current user.
- [ ] Predicted and corrected values plus correction history are preserved.
- [ ] Only verified receipts are exported by default.

## OCR owner

- [ ] I accept `receipt_id` and a local image path from the worker.
- [ ] I return `schema_version`, engine metadata, image dimensions and blocks.
- [ ] Every block has text, confidence, a four-point normalized polygon and reading order.
- [ ] Polygon point order and coordinate origin match the shared convention.
- [ ] I return an empty block list for no detections and a typed error for engine failure.
- [ ] I do not write directly to Backend's database.

## KIE owner

- [ ] I accept the engine-independent OCR result schema.
- [ ] I always return exactly the five required field keys.
- [ ] My normalized types are string/date/integer as specified.
- [ ] Missing values use `null`, confidence `0` and an empty source list.
- [ ] Every `source_block_id` exists in the OCR input.
- [ ] Field confidence means confidence in the normalized business value.

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
| Raw field property | `raw_text` | KIE + Backend | Pending |
| OCR source reference | `source_block_ids` array | OCR + KIE | Pending |
| Total canonical type | Integer VND | KIE + Backend | Pending |
| Date canonical type | ISO `YYYY-MM-DD` | KIE + Backend | Pending |
| Queue implementation | Redis/Celery | Backend + DevOps | Pending |
| Upload maximum | 10 MiB | Backend + Frontend | Pending |
| Allowed formats | JPEG, PNG, WebP | Backend + Frontend | Pending |

## Sign-off

| Role | GitHub username | Date | Result |
| --- | --- | --- | --- |
| Frontend |  |  | Pending |
| Backend |  |  | Pending |
| OCR |  |  | Pending |
| KIE |  |  | Pending |
| DevOps/Lead |  |  | Pending |
