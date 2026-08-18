# DevOps W1 delivery checklist

Date assessed: 2026-08-17 (updated; originally 2026-08-14)
Branch: `feat/devops-local-infra-foundation`

This checklist compares the DevOps baseline in the repository with the
attached W1 requirements. `Done` means the requirement has been implemented
and verified. **All ten requirements are Done.**

| Requirement | Status | Evidence / note |
| --- | --- | --- |
| 1. Docker Compose local stack | Done | `docker-compose.yml` starts PostgreSQL, Redis, MinIO, `minio-init`, Backend, Worker and Frontend on `vietreceipt_internal`, with stable service names and named volumes. |
| 2. PostgreSQL | Done | Environment-based bootstrap, healthcheck, `postgres_data` volume and `DATABASE_URL` using the `postgres` service name are configured. |
| 3. Redis | Done | Redis has a healthcheck, AOF-backed `redis_data` volume and documented `REDIS_URL`/Celery URLs using the `redis` service name. |
| 4. MinIO / object storage | Done | MinIO has environment credentials, `minio_data` volume, healthcheck, exposed API/console ports and idempotent private-bucket bootstrap in `infra/minio/bootstrap.sh`. |
| 5. Shared environment configuration | Done | `.env.example` defines canonical `DATABASE_URL`, `REDIS_URL`, Celery and `STORAGE_*` variables, plus `BACKEND_PORT`/`FRONTEND_PORT` Compose overrides. W1 runtime storage is frozen as `STORAGE_BACKEND=filesystem`; MinIO remains a provisioned S3-compatible dependency for later migration. Uses `STORAGE_*` instead of the `S3_*` names listed in the original task text — **confirmed correct by Backend owner on 2026-08-17**. |
| 6. Healthchecks | Done | PostgreSQL, Redis, MinIO, Backend and Worker are healthchecked; worker visibility uses `celery inspect ping`. Frontend (Next.js dev server) has no cheap health endpoint, so it is checked at the HTTP level by the smoke test instead of a Compose healthcheck. Backend's probe targets `/openapi.json` as an accepted interim endpoint — see follow-up below. |
| 7. Local developer workflow | Done | `infra/README.md` documents start, status, logs, stop, reset, all six service endpoints and the destructive-volume warning. Root `README.md` now links to it. |
| 8. CI foundation | Done | Workflow `.github/workflows/backend-and-infra.yml` runs Backend tests (122 cases) and the infrastructure smoke test, including Backend/Worker health and Backend→Postgres/Redis/MinIO DNS resolution. **A successful workflow run exists on the PR.** |
| 9. Security baseline | Done | `.env` and local data are ignored, `.env.example` contains placeholders only, MinIO bucket is private, and bootstrap/smoke commands do not print credentials. Production secret management is explicitly out of W1 scope. |
| 10. Ownership boundary | Done | No FastAPI business endpoint, Worker task, storage adapter rewrite, repository/business persistence, OCR or KIE implementation was added. Backend container runs Backend-1's own `app/main.py` unmodified; Worker container has zero registered tasks. |

**Note on requirement 5:** the original task text lists `S3_ENDPOINT_URL`,
`S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`. This repository's
canonical names are `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`,
`STORAGE_SECRET_KEY`, `STORAGE_REGION` (Backend-2's existing convention,
documented in `backend/README.md`). Introducing a second `S3_*` group would
duplicate canonical config, which the task explicitly prohibits.
**Confirmed by the Backend owner on 2026-08-17: `STORAGE_*` is correct;
no rename needed.**

**Note on Backend vs. Worker container status:** Backend's FastAPI
entrypoint (`backend.app.main:app`) exists and is fully wired
(`infra/docker/backend.Dockerfile`, confirmed against the Backend owner's
documented module path/command/dependency contract). Worker is different:
no concrete Celery application, module path or pinned Redis/Celery
dependency exists anywhere in the repository yet, so `infra/docker/worker/`
is a **DevOps-owned skeleton with zero registered tasks**.

This satisfies W1: the task explicitly asks for a "Worker
container/skeleton", not a processing worker. Replacing the skeleton with
a real application worker is **follow-up work under Issue #21 (Backend
processing integration), not a blocker for this task**. The real
processing path — `enqueue receipt_id → worker claim → PROCESSING → OCR →
KIE → NEEDS_REVIEW` — is receipt-processing business semantics owned by
Backend-1.

## Ownership boundary

| Owner | Owns |
| --- | --- |
| **Backend-1** | `ProcessingScheduler` semantics; application queue adapter; processing job payload; worker handler/orchestration; receipt state transitions; retry/idempotency/business failure semantics |
| **Backend-2** | persistence; storage abstraction/adapters; repository/application persistence services |
| **DevOps** | Redis/Celery runtime; worker container/process; broker configuration; networking; healthchecks; logs/runtime visibility; CI/local environment |

DevOps owns the worker **container and process** (Dockerfile, broker
config, healthcheck, log visibility). Backend-1 owns the worker
**handler and orchestration** (which tasks run, what they do, how they
retry). **DevOps does not own receipt-processing business semantics.**

## Definition of Done comparison

Completed locally:

- [x] Docker Compose configuration validates and starts Postgres, Redis, MinIO, Backend, Worker and Frontend.
- [x] PostgreSQL, Redis, MinIO, Backend and Worker become healthy.
- [x] PostgreSQL, Redis and MinIO use persistent named volumes.
- [x] Shared environment variables and `.env.example` are documented.
- [x] No real secret was added; MinIO bootstrap creates a private bucket.
- [x] Infrastructure services resolve through Compose service names — proven from inside the `backend` container itself (`getent hosts postgres redis minio`), not just from `postgres`.
- [x] Local setup, health checks and reset instructions are documented.
- [x] CI foundation is present and covers Backend/Worker health and DNS resolution.
- [x] No Backend-1/Backend-2 implementation was duplicated.
- [x] Local smoke evidence passed: persistence checks, 122 Backend tests, and the full contract suite (9 positive + 23 negative cases).

- [x] Branch pushed and PR opened; GitHub Actions ran successfully on the PR.

**All Definition of Done items are met. DevOps W1 is complete.**

## Follow-up work (not blocking this task)

- Replace the DevOps-owned Worker skeleton with the real application
  worker once Backend-1 commits a concrete Celery application and its
  pinned dependencies. Tracked under **Issue #21 (Backend processing
  integration)** — the W1 requirement was a worker container/skeleton,
  which is already delivered.
- Switch the `backend` healthcheck from `/openapi.json` to `/healthz`
  once Backend ships a canonical health endpoint. `/openapi.json` is an
  accepted interim probe for this infrastructure foundation. DevOps must
  **not** add a fake business/API endpoint just to serve a healthcheck.

## Local evidence command

```bash
cp .env.example .env
PYTHON_BIN=.venv/bin/python ./infra/scripts/smoke-test.sh
```

The command passed locally on 2026-08-17. It validates Compose, health for
all provisioned + application services, private-bucket bootstrap, internal
DNS (including from the `backend` container), volume persistence,
service-name resolution, 122 Backend tests and the shared contract suite.
