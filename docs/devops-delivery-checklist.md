# DevOps W1 delivery checklist

Date assessed: 2026-08-17 (updated; originally 2026-08-14)
Branch: `feat/devops-local-infra-foundation`

This checklist compares the DevOps baseline in the repository with the
attached W1 requirements. `Done` means the requirement has been implemented
and verified locally. `Partial` means a dependency or required evidence is
still missing.

| Requirement | Status | Evidence / note |
| --- | --- | --- |
| 1. Docker Compose local stack | Done | `docker-compose.yml` starts PostgreSQL, Redis, MinIO, `minio-init`, Backend, Worker and Frontend on `vietreceipt_internal`, with stable service names and named volumes. |
| 2. PostgreSQL | Done | Environment-based bootstrap, healthcheck, `postgres_data` volume and `DATABASE_URL` using the `postgres` service name are configured. |
| 3. Redis | Done | Redis has a healthcheck, AOF-backed `redis_data` volume and documented `REDIS_URL`/Celery URLs using the `redis` service name. |
| 4. MinIO / object storage | Done | MinIO has environment credentials, `minio_data` volume, healthcheck, exposed API/console ports and idempotent private-bucket bootstrap in `infra/minio/bootstrap.sh`. |
| 5. Shared environment configuration | Done | `.env.example` defines canonical `DATABASE_URL`, `REDIS_URL`, Celery and `STORAGE_*` variables, plus `BACKEND_PORT`/`FRONTEND_PORT` Compose overrides. W1 runtime storage is frozen as `STORAGE_BACKEND=filesystem`; MinIO remains a provisioned S3-compatible dependency for later migration. Uses `STORAGE_*` instead of the `S3_*` names listed in the original task text — **confirmed correct by Backend owner on 2026-08-17**. |
| 6. Healthchecks | Done | PostgreSQL, Redis, MinIO, Backend and Worker are healthchecked. Frontend (Next.js dev server) has no cheap health endpoint, so it is checked at the HTTP level by the smoke test instead of a Compose healthcheck. |
| 7. Local developer workflow | Done | `infra/README.md` documents start, status, logs, stop, reset, all six service endpoints and the destructive-volume warning. Root `README.md` now links to it. |
| 8. CI foundation | Done | Workflow `.github/workflows/backend-and-infra.yml` runs Backend tests (122 cases) and the infrastructure smoke test, including Backend/Worker health and Backend→Postgres/Redis/MinIO DNS resolution. |
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
is a **DevOps-owned skeleton with zero registered tasks**, not an
integration of a real entrypoint. It must be replaced once Backend/Worker
owners commit a real Celery app — see `docs/implementation-notes.md`.

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

Still required before marking the whole attached DevOps task fully Done:

- [ ] Push this branch (already includes a merge of `origin/main`) and open a PR; attach the successful GitHub Actions workflow link/log as reproducibility evidence.
- [ ] Replace the DevOps-owned Worker skeleton once Backend/Worker owners commit a concrete Celery application (module path + pinned dependencies).

## Local evidence command

```bash
cp .env.example .env
PYTHON_BIN=.venv/bin/python ./infra/scripts/smoke-test.sh
```

The command passed locally on 2026-08-17. It validates Compose, health for
all provisioned + application services, private-bucket bootstrap, internal
DNS (including from the `backend` container), volume persistence,
service-name resolution, 122 Backend tests and the shared contract suite.
