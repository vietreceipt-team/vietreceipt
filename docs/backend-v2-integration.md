# Backend V2 integration — 01/10/2026

## Teammate changes reviewed

The current `main` already includes TV3 [#55](https://github.com/vietreceipt-team/vietreceipt/pull/55), TV4 [#58](https://github.com/vietreceipt-team/vietreceipt/pull/58), TV5 [#53](https://github.com/vietreceipt-team/vietreceipt/pull/53) and TV6 [#54](https://github.com/vietreceipt-team/vietreceipt/pull/54). Historical V1 branches were compared, not merged wholesale into V2. The isolated push-event CI fix on `fix/kie-ci-push-whitespace` (`b61acba`) was adapted to the current workflow, including first-push handling.

After these merges, nine local backend tests failed because their producers still emitted the earlier incomplete V2 schema; PostgreSQL CI had the same issue. KIE CI additionally used an empty PR base reference on push. Both are corrected here.

## Integrated behavior

- Unset provider settings now select `ai.document_reader.backend:read_document` and `ai.kie.v2:extract_invoice`. Explicit empty/invalid settings still fail clearly. Reader errors retain their canonical backend class, code and retryability. OCR/model failures can be retried after runtime repair; invalid/corrupt documents remain nonretryable.
- PDFium words are joined into adjacent spatial spans by baseline overlap and font-relative gaps. This supports multiword KIE labels without the ignored local demo shim, while keeping table gutters. Explicit note/signature/thank-you footers end table regions; incomplete data rows remain reviewable. KIE extractor version is `2.0.1`.
- Backend validation uses TV4's cross-record validator, including exact immutable raw text, source order and aggregate row metadata. Invalid results fail before publishing review cells.
- Upload accepts up to 30 PDF pages, matching the default reader. Celery uses the dedicated `vietreceipt-v2` queue; outbox, lease fencing, recovery and optimistic review concurrency remain active.
- Invoice list includes effective invoice number and currency, and loads headers in one batch. Frontend avoids one detail request per invoice when these summary fields exist, while retaining compatibility with older servers.
- Verified JSON includes OCR/KIE identities and per-cell value statuses. CSV/XLSX append status columns and a tax row ID, so reviewed UNKNOWN/UNREADABLE/NOT_PRESENT values remain distinguishable after export. Existing value columns and linked tables are retained.
- `backend/requirements-ai.txt` combines real worker dependencies with backend pins without contradictory JSON Schema versions. Shared OCR pins retain the existing Paddle versions and include compatible setuptools. Compose has a lightweight API/beat/migration target, a complete CPU worker target, shared source storage and persistent model cache.

## Verification

On Python 3.12, with a separately migrated PostgreSQL 16 database:

```sh
PYTHONPATH=.:backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 TEST_DATABASE_URL=postgresql+psycopg://... \
  python -m pytest backend/tests tests -q
python tests/contracts/run_contract_tests.py
```

Results: **304 tests and 107 subtests passed**, including PostgreSQL two-worker claim/correction races, SQLite foreign keys, real single/multipage text PDF → KIE → review → all three exports, invalid provenance rejection, reviewed uncertainty export and batch list queries. Shared V1/V2 contracts pass. Frontend typecheck/lint/build, **55 unit tests and 17 browser tests** pass.

Real HTTP smoke used Uvicorn, PostgreSQL 16, Redis and Celery worker/beat with the actual TV3/TV4 providers, on synthetic Vietnamese invoices only:

| Route | Receipt | Machine result | Human review | Result |
| --- | --- | --- | --- | --- |
| Text PDF | `61b19764-a76a-46d0-8633-f139be65bb9d` | All 13 headers match the synthetic reference; 2 lines, 1 tax group | Explicitly confirm machine values | VERIFIED; JSON/CSV/XLSX downloaded |
| PNG | `33f8798b-843a-463a-a8e2-4d81018e75b1` | 13 header cells, 2 lines, 1 tax group; OCR text errors and null/ambiguous cells | Explicit corrections from the synthetic reference | VERIFIED; JSON/CSV/XLSX downloaded |
| Scanned PDF | `b6620478-4410-47e4-a99c-097b4c2b5b14` | 13 header cells, 2 lines, 1 tax group; OCR text errors and null/ambiguous cells | Explicit corrections from the synthetic reference | VERIFIED; JSON/CSV/XLSX downloaded |

Local evidence, attempt/OCR/KIE IDs and service logs are in ignored `.data/backend-integration/`. `smoke-v2.py --expected-json` checks machine results; `--review-json` applies explicit synthetic human reference corrections and records machine/reviewed headers separately. Corrected output is not OCR accuracy evidence.

## Remaining acceptance limits

The full Compose images build and pass dependency checks on Docker Desktop ARM64. PostgreSQL migration, readiness, and text PDF upload → extraction → review → JSON/CSV/XLSX pass (`6b99521c-b7e8-4f98-bd4e-804709da2a4e`). Image/scan OCR in this Linux ARM64 image exits with a native Paddle SIGSEGV, including a standalone process with `OMP_NUM_THREADS=1`; changing Celery pool alone does not resolve it. Docker ARM64 image/scan support is therefore not verified. Use the verified native macOS Python 3.12 worker for the local demo. The container defaults to one OpenMP thread as recommended by its Paddle runtime. Linux ARM64 Paddle compatibility remains a separate runtime issue.

Image/scan OCR still needs human comparison, including apparently PRESENT names. The baseline does not promise perfect extraction. Synthetic smoke and software regression tests do not establish accuracy, latency or robustness on frozen unseen documents. Leader sign-off and research evaluation remain separate; no project issues are automatically closed by this integration.

## English/USD demo correction — 05/10/2026

KIE 2.0.2 / configuration 2.1.0 supports calendar-validated English month names, explicit USD codes and two-decimal amounts, To/Bill-to buyer sections, wrapped names/addresses, reviewed company letterheads and service revenue/amount tables. Foreign printed Taxcode identifiers are preserved; bank remittance data is not treated as seller/buyer identity. VND normalization remains unchanged. The money schema accepts numeric USD amounts; shared/backend validation enforces currency precision and review corrections accept cents only for USD. VND-only arithmetic diagnostics are skipped on USD documents.

Verification: 306 Python tests and 107 subtests passed; the PostgreSQL race test was skipped locally because Docker was stopped. Shared contracts, frontend typecheck/lint/build, 55 unit tests and 18 browser tests passed, including USD decimal editing. A real English text PDF goes through reader/KIE, optimistic review, verification and JSON/CSV/XLSX export, including rejection of three-decimal USD corrections. Synthetic regression fixtures use fictional names and different dates/amounts; user documents are not committed.

The user's image was processed again through the native OCR worker and now extracts its English date, USD total, seller/buyer names, seller address, printed buyer Taxcode and one service row. This new review record preserves the old receipt and remains unverified. Unprinted template/symbol, seller tax ID, subtotal/tax and absent quantity/unit-price values still require explicit human review rather than fabricated values. A company-letterhead role and wrapped service description are also flagged for confirmation.
