# Backend V2: reproducible experiments and a real workflow demo

## What is recorded

`python -m scripts.evaluate_backend_v2` uploads a **new receipt per sample** through HTTP and waits for the real outbox/Redis/Celery worker. It does not process in the API process or select a fake provider. Real mode checks both the configured TV3/TV4 paths and the callables actually dispatched by the worker; CI doubles require `--mode test`.

Each fresh output directory contains:

- `manifest.json`: exact dataset/version/split/provenance and sample specification; `run.json`: manifest hash, runner commit/dirty flag, Python, mode, polling/timeout/review configuration and timing/metric policy.
- `<sample>/result.json`: SHA-256 of the bytes actually uploaded, receipt ID, condition, status, client upload/queue+processing/total wall time, failures and export checksums. Missing files, hash mismatches, timeouts and failed reads remain in the summary denominator; the CLI exits nonzero if any sample fails.
- `<sample>/machine/snapshot.json`: **original, immutable** OCR/KIE runs, attempt linkage, success/failure, actual worker commit/source checksum, architecture, resolved package versions, selected providers, reader/KIE configuration, model artifact checksums and stage durations. Separate `ocr-<run>.json` and `kie-<run>.json` are the provider payloads without effective/corrected values.
- `<sample>/reviewed/`: opt-in synthetic corrections, reviewed detail and verified JSON, CSV ZIP and XLSX. The runner parses each export and checks explicit header corrections, then fetches the machine snapshot again and requires byte-equivalent JSON data. Reviewed outputs are **workflow evidence, never AI accuracy predictions**.

Existing runs are never overwritten. Use a different `--output` for each repeat. An absent worker commit/model cache or a dirty source tree is recorded explicitly, not inferred from the client checkout. Docker must be built with `VIETRECEIPT_COMMIT` to record its declared source revision; source SHA and packages additionally identify its bytes/runtime. Worker Git identity is captured once per process; restart the worker after code/config changes. No connection URLs or credentials are collected.

Attempt metadata is added by migration `20261023_provenance`, nullable for legacy attempts. No old machine payloads, corrections or receipts are rewritten. `GET /api/v2/receipts/{id}/machine-results` exposes all attempts and immutable runs, including failures; `/evidence` and the existing detail/review/export API stay compatible. Stage times include validation and subprocess/model initialization, and total worker time is captured before transaction commit. Client wall times include queue/poll overhead; they are not warm-model inference timings.

## Generate and run the three-format demonstration

Use Python 3.12 and the repository's real pinned runtime:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt -r backend/requirements-ai.txt
python -m scripts.create_v2_demo --output results/demo-inputs
```

This creates a fictional text PDF, JPG and image-only scan PDF from **one template**, with a versioned, checksummed manifest. It is not the frozen final test set. Expected demo correction: invoice number becomes `DEMO-REVIEWED`; original machine output is retained.

Against a running API/worker:

```sh
python -m scripts.evaluate_backend_v2 \
  --manifest results/demo-inputs/manifest.json \
  --output results/demo-run-001 --url http://127.0.0.1:8000 \
  --review-synthetic
```

`--review-synthetic` is an explicit test-review action, allowed only for manifests with `synthetic: true` and split `demo`/`development`. It confirms remaining flagged values/statuses only on the receipts uploaded by this run. Never use it for user receipts or final-test accuracy. For ordinary research capture, omit the flag: records stop at NEEDS_REVIEW and only machine artifacts are collected. A sample may supply `review.header`, `review.line_items` and `review.tax_breakdown`; structured row counts must match rather than silently dropping/adding rows.

A timeout produces partial evidence and a failing exit code. It does not cancel a remote task or automatically retry/replay the sample. Failed processing is retried explicitly with the existing optimistic-version API after the runtime has been repaired.

## Docker and ARM64

Use a separate Compose project/port to avoid another local demo's database or queue:

```sh
export VIETRECEIPT_COMMIT="$(git rev-parse HEAD)"
export BACKEND_V2_PORT=18026
docker compose -p vietreceipt-v2-demo -f docker-compose.v2.yml up -d --build
# API: http://127.0.0.1:18026/docs
```

The API/migration/beat use the lightweight runtime; only the worker includes Paddle. Persistent source storage/model cache and the dedicated queue are unchanged. `pip check` runs during the worker build.

The pinned Paddle 3.0.0 / PaddleOCR 3.0.3 / PaddleX 3.0.3 **still crashes with SIGSEGV (-11) on the tested Linux aarch64 image for JPG and scanned PDF**. PDF text succeeds. A subprocess boundary is now the default (`V2_READER_ISOLATION=subprocess`): the attempt becomes FAILED with retryable `DOCUMENT_READER_CRASHED`, retaining error/provenance, and the Celery worker continues processing later text PDFs without restarting. This contains the crash; it does not claim to repair Paddle inference. An analogous upstream report is [PaddleOCR #16685](https://github.com/PaddlePaddle/PaddleOCR/issues/16685); our acceptance evidence is the local pinned-runtime test, not a guarantee inferred from that issue.

`V2_READER_TIMEOUT_SECONDS` defaults to 780, must be finite and in `(0, 800]`, below the worker's 840/870-second limits and default 900-second lease. Timeout kills/waits for the child and reports `DOCUMENT_READER_TIMEOUT`. `inprocess` is an explicit diagnostic/performance opt-in and loses this native-crash boundary; invalid mode/timeout fails clearly. Original nonretryable reader errors, including corrupt PDF, retain their code and retryability. Isolation intentionally reloads models per document; account for this in latency experiments.

For a compatibility worker on an ARM64 Docker host, the optional overlay emulates **only the worker**, keeping the other services host-native:

```sh
docker compose -p vietreceipt-v2-demo \
  -f docker-compose.v2.yml -f docker-compose.v2.amd64.yml up -d --build
```

The [acceptance run](v2-stability-acceptance.md) completed all three formats with this AMD64 worker on the tested ARM64 host. Native macOS ARM64 Python 3.12 with the pinned real providers also completed all three formats. Linux ARM64 inference remains unsupported by this pinned runtime; select the overlay explicitly for a Docker demo on this host.

To run a native worker with containerized PostgreSQL/Redis, expose dedicated local database/broker ports, migrate an isolated database and set the **same** DATABASE_URL, CELERY_BROKER_URL, STORAGE_FILESYSTEM_ROOT and pinned Python environment for API, worker and beat:

```sh
python -m alembic -c backend/alembic.ini upgrade head
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18027
# Other terminals with the same environment:
python -m celery -A backend.app.v2.worker:celery_app worker --pool=solo --concurrency=1
python -m celery -A backend.app.v2.worker:celery_app beat --schedule=/tmp/v2-demo-beat
```

Do not run a second worker on another experiment's Redis DB/queue. For UI demonstration, start `frontend/server.js` with `FRONTEND_DATA_MODE=api BACKEND_API_ORIGIN=http://127.0.0.1:18027` and a dedicated port; no mocked receipts are inserted.

## Regression and CI

```sh
PYTHONPATH=.:backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  TEST_DATABASE_URL=postgresql+psycopg://... \
  python -m pytest backend/tests tests -q
python tests/contracts/run_contract_tests.py
python -m scripts.export_openapi_v2
git diff --check
```

TV5 CI now runs the manifest runner on JPG/text PDF/scan PDF using explicitly labelled test providers and uploads its artifacts. This checks workflow/reproducibility, not OCR quality. Native crash/timeout containment, retry history, machine immutability across correction, real-provider identity enforcement, additive migration, checksum failures, missing inputs/timeouts and export parsing have regression coverage. The existing PostgreSQL race, stale-version, verification gate, export-safety and real text-PDF/KIE tests remain active.


## TV2 development handoff and report tables (23 October)

The new TV2 candidate package in PR #66 contains original development inputs.
It has **PENDING_REVIEW** gold: integrity/hash freeze does not authorize accuracy
scoring or final-test access. To capture backend machine results, extract the
checksummed `data/handoffs/tv4-dev-v1.zip` from the pinned TV2 source revision
outside Git, then run:

```sh
python -m scripts.prepare_tv2_backend_manifest \
  --root results/tv2-handoff \
  --output results/tv2-validation-inputs \
  --source-revision 8a603300071d6dbfebd23e8f22a8c9cbac90ff48
python -m scripts.evaluate_backend_v2 \
  --manifest results/tv2-validation-inputs/manifest.json \
  --output results/tv2-backend-run-001 --url http://127.0.0.1:18026
```

The importer validates both train and validation membership/counts, source hashes,
source paths and cross-split parent/template/content identity before creating output.
It copies **every validation source**, even if TV2's prior reader failed. It does
not copy prior OCR/KIE, align IDs, read final mock/test manifests, run training
inputs, grant QA, or attach automatic corrections. It preserves pending QA,
source revision declaration and both manifest hashes. Rerun on original bytes
creates new server receipt/run IDs; old block alignment is not valid for the new
run without renewed alignment/QA. Changing the protocol/source matcher requires
separate owner review, not renaming the pending labels to VERIFIED.

Every HTTP run now emits these alongside the per-sample directories:

| Artifact | Use |
|---|---|
| `machine_predictions.jsonl` | One row per attempted source, including errors; original OCR/KIE runs and attempt provenance only |
| `run_metadata.json` | Runner identity/config plus dataset/version/split/QA/provenance; links to machine results |
| `samples.csv` | One row per attempt with source hash, receipt, processing success, workflow state and client/worker stage times |
| `failures.csv` | All failed samples, typed code, stage and elapsed times; empty failures still emit a header |
| `metrics.json`, `metrics.csv` | System processing/workflow counts; `accuracy: null`, `NOT_SCORED` |

All intended sources remain in the denominator, with not-attempted count visible
for an interrupted run. `processing_success_rate` uses the intended cohort;
check `complete` and attempted/not-attempted before interpreting it. Processing
success requires reviewable structured output and valid selected-run provenance;
a later review/export failure remains a workflow failure without rewriting the
machine-processing result. Client total includes review/export when enabled;
`processing_wall_ms` ends at the processing terminal state. Queue/poll overhead
is included; model/subprocess startup is included in worker document-reading time.
Partial runs are not final benchmark results.

Console output uses sample ordinal/status rather than source names. Failure summaries
omit raw exception messages, URLs, credentials, invoice text and local file paths.
Raw machine artifacts intentionally contain document text and must be handled with
the dataset's access permissions. No user documents are committed. Existing run
folders are still refused rather than overwritten; a detected changed snapshot is
not overwritten by the post-review response.

TV1 PR #64 is a proposed protocol, not final approval. TV4's USD validation fix
PR #63 is merged, but required UNKNOWN/strict-completion policy, row precision/F1
and a source-region matcher remain separate gates. This capture runner neither
reruns KIE on prepared OCR and calls it end-to-end nor substitutes corrected
values for machine predictions. See [TV5 incremental status](tv5-progress-20261023.md).
