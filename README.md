# VietReceipt - Week 1 Backend Contract Pack

Status: **Draft v1.3 - integration re-review requested**
Owner: Backend / System Architecture
Scope: Core receipt digitization flow with five fields: `merchant_name`, `receipt_date`, `total_amount`, `invoice_id`, `merchant_address`.

## Deliverables

| File | Purpose |
| --- | --- |
| `docs/architecture.md` | Overall architecture and module communication decisions |
| `docs/receipt-state-machine.md` | Receipt lifecycle, valid transitions and invariants |
| `docs/integration-contracts.md` | Shared OCR/KIE data contracts and integration conventions |
| `docs/git-workflow.md` | Repository, branch, commit, PR and task conventions |
| `openapi/openapi.yaml` | API Contract v1 for Frontend and Backend |
| `schemas/ocr-result.schema.json` | Machine-readable OCR output schema |
| `schemas/kie-result.schema.json` | Machine-readable KIE output schema |
| `examples/*.json` | Valid sample payloads for OCR and KIE |
| `docs/annotation-contract.md` | Shared ground-truth envelope aligned with KIE guideline v1.1 |
| `schemas/annotation-record.schema.json` | Machine-readable ground-truth annotation schema |
| `scripts/validate_annotation_ocr.py` | Cross-record receipt/OCR run/block validator |
| `tests/contracts/` | Python-only positive and negative contract suite |
| `requirements-contracts.txt` | Exact Python dependency pin for contract validation |
| `docs/review-checklist.md` | Sign-off checklist for all five members |

## Decisions fixed in v1

- Architecture: modular monolith with a separate background worker.
- Frontend communicates only with FastAPI through REST/JSON; image upload uses `multipart/form-data`.
- Long-running OCR/KIE work is asynchronous. Frontend polls receipt status; it never calls OCR/KIE directly.
- Backend automatically schedules processing after upload; Frontend does not call a public `/process` endpoint. `UPLOADED` means persistence is committed, while `PROCESSING` begins only when a worker claims/starts an attempt.
- Successful enqueue does not change public state. Scheduling/enqueue failure after commit transitions the receipt to `FAILED` with `stage=SCHEDULING` and `retryable=true`.
- The public receipt lifecycle contains exactly `UPLOADED`, `PROCESSING`, `NEEDS_REVIEW`, `VERIFIED` and `FAILED`; queue state is internal.
- Backend API and worker share Python domain packages and Pydantic models.
- Worker receives only a `receipt_id`; it loads image metadata/storage key from PostgreSQL, downloads the image, then invokes OCR and KIE.
- PostgreSQL is the source of truth for metadata, status, OCR blocks, extracted fields and correction history.
- MinIO/S3-compatible storage is the source of truth for receipt image bytes.
- Redis/Celery is the proposed task transport for the first deployed version. The domain contract does not depend on Celery and may be executed synchronously in tests.
- Receipt, user and database entity identifiers are UUID strings. OCR `block_id` is an opaque string unique within one OCR run (for example `block_12`). A later OCR run may reuse the same local block IDs.
- Timestamps are RFC 3339 UTC strings, for example `2026-08-10T08:30:00Z`.
- OCR coordinates are normalized to `[0, 1]`, relative to the exact image dimensions returned in the OCR result.
- `total_amount` is a non-negative integer in VND; `receipt_date` is ISO `YYYY-MM-DD`; unavailable values use `null` plus an explicit status.
- Every KIE result contains all five field keys, even when a field could not be found.
- A KIE field may reference multiple OCR blocks through `source_block_ids`.
- OCR and KIE runs are immutable and linked through `ocr_run_id`, `kie_run_id` and `source_ocr_run_id`.
- Raw, predicted, normalized, corrected and effective values have distinct owners and semantics.
- Public correction addressing uses a canonical field name and one `APPLY`/`CLEAR` request contract. Correction and verification reject stale `expected_updated_at` tokens with HTTP `409`.

## Items requiring OCR/KIE sign-off

The v1 draft is usable immediately, but it is not final until the OCR and KIE owners confirm:

1. OCR can always provide a four-point polygon and block confidence in `[0, 1]`.
2. OCR reading order is deterministic and zero-based.
3. KIE accepts the normalized OCR result without engine-specific fields.
4. KIE returns all five keys and uses the canonical types defined here.
5. KIE owns field-level confidence and immutable `machine_needs_review`; Backend derives `effective_needs_review` after correction/verification. Numeric thresholds remain provisional/TBD until calibration.

## Differences found in the current OCR/KIE README files

The current OCR README specifies text, confidence and bounding box but does not yet fix block ID, polygon shape, coordinate system, reading order or result envelope. The current KIE README example uses `raw_value`, a string `"325000"`, and singular `source_block_id`.

Following the KIE Owner reviews, v1.3 separates machine review signals from the current human-review state. `effective_value` uses a correction when one exists and otherwise uses only `normalized_value`; it never falls back to `predicted_value`. Re-review remains required before merge.

If an owner cannot meet one of these requirements, change the shared schema through a reviewed Pull Request instead of adding an undocumented field.

## Suggested Git handoff

Create one documentation Issue, for example `#12`, then:

```bash
git checkout main
git pull origin main
git checkout -b docs/12-week1-backend-contract
```

Place this pack in the repository, commit logical groups, push, and open a Pull Request containing `Closes #12`.

Suggested commits:

```text
docs(architecture): define module communication and receipt lifecycle
docs(api): add OpenAPI contract v1
docs(integration): add shared OCR and KIE schemas
docs(project): document Git workflow and contract review checklist
```

## Definition of Done

Week 1 is complete only when:

- OpenAPI parses successfully and example payloads conform to the shared schemas.
- Frontend, Backend, OCR, KIE and DevOps owners have reviewed the pack.
- Every owner can state what their module receives, what it returns and how errors are represented.
- All questions in `docs/review-checklist.md` are resolved.
- The Pull Request is approved and merged into `main`.
