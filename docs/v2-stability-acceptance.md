# V2 stability acceptance — 23/10/2026

Synthetic workflow tests only: one fictional invoice template rendered as JPG, text PDF and image-only scanned PDF. No private user receipts or frozen unseen test data were used. Original AI predictions are not replaced with reviewed values or used to claim accuracy.

| Runtime | JPG | Text PDF | Scanned PDF | Worker after native crash |
|---|---|---|---|---|
| Native macOS ARM64, Python 3.12, pinned TV3/TV4 | VERIFIED + JSON/CSV/XLSX | VERIFIED + JSON/CSV/XLSX | VERIFIED + JSON/CSV/XLSX | Crash/timeout/retry regression tests pass |
| Docker Linux aarch64, pinned Paddle | FAILED, exit -11 | VERIFIED + JSON/CSV/XLSX | FAILED, exit -11 | Same worker processes an additional text PDF successfully, without restart |
| Docker Linux x86_64 worker emulated on ARM64, `docker-compose.v2.amd64.yml` | VERIFIED + JSON/CSV/XLSX | VERIFIED + JSON/CSV/XLSX | VERIFIED + JSON/CSV/XLSX | Compatibility route; API/PostgreSQL/Redis remain host-native |

Each successful run uses actual HTTP upload, outbox, Redis, Celery, PostgreSQL, configured TV3 document reader and TV4 Invoice KIE. The explicit synthetic reviewer changes the invoice number to `DEMO-REVIEWED`, confirms remaining flagged values/statuses, verifies, parses all three exports and requires the machine-results snapshot to remain unchanged. Export CSV is a ZIP of linked tables, rather than a single flat file. Source hashes and all attempt/run IDs are saved by the runner.

The clean native run records feature commit `277fe71` with `git_dirty: false`, arm64 architecture, actual stage timings, 15 cached model artifact hashes and full resolved package versions. Docker runs separately record their declared build revision, source checksum and actual aarch64/x86_64 architecture. Running from an uncommitted checkout or building without the commit argument is visible in provenance; the runner's own checkout revision is separate from the server worker's identity.

Local regression verification:

- **322 Python tests and 107 subtests pass** against a separately migrated PostgreSQL test database; no PostgreSQL race test is skipped.
- **181 backend tests pass** when run with the same test-provider environment variables used by TV5 CI. Native-failure tests explicitly select the real reader adapter before simulating its crash; they do not inherit CI's fake reader.
- Shared V1/V2 schema, correction/concurrency and provenance contracts pass.
- Ruff, formatting and `git diff --check` pass.
- Docker ARM64 and AMD64 worker images build and `pip check` passes; additive migration/readiness pass.
- Frontend typecheck/lint/build and **55 unit tests pass**, preserving the existing review UI/API contract. No new browser E2E pass is claimed.

The original Linux ARM64 Paddle engine problem is still present. Isolation fixes receipt/worker failure handling, and the explicit AMD64 overlay supplies a tested Docker demo route on this Apple Silicon host. Native model output may still contain OCR/KIE errors requiring human review. Compatibility/emulation and synthetic software tests do not establish accuracy, throughput, robustness or final-test performance on other hardware/datasets.

Run commands, artifact layout, timeout behavior, migration and evidence boundaries are in [v2-reproducible-demo.md](v2-reproducible-demo.md). PR [#62](https://github.com/vietreceipt-team/vietreceipt/pull/62) contains the CI results. Full generated synthetic evidence and service logs remain in ignored `.data/` and the separate delivery output; user data/models/credentials are not committed.
