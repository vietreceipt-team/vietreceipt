# DevOps W1 delivery checklist

Date assessed: 2026-08-14  
Branch: `feat/devops-local-infra-foundation`

This checklist compares the DevOps baseline in the repository with the
attached W1 requirements. `Done` means the requirement has been implemented
and verified locally. `Partial` means a dependency or required evidence is
still missing.

| Requirement | Status | Evidence / note |
| --- | --- | --- |
| 1. Docker Compose local stack | Partial | `docker-compose.yml` starts PostgreSQL, Redis, MinIO and the `minio-init` bootstrap service on `vietreceipt_internal`, with stable service names and named volumes. Backend API and Worker services are intentionally not included because their runnable entrypoints have not yet been delivered. |
| 2. PostgreSQL | Done | Environment-based bootstrap, healthcheck, `postgres_data` volume and `DATABASE_URL` using the `postgres` service name are configured. |
| 3. Redis | Done | Redis has a healthcheck, AOF-backed `redis_data` volume and documented `REDIS_URL`/Celery URLs using the `redis` service name. |
| 4. MinIO / object storage | Done | MinIO has environment credentials, `minio_data` volume, healthcheck, exposed API/console ports and idempotent private-bucket bootstrap in `infra/minio/bootstrap.sh`. |
| 5. Shared environment configuration | Done | `.env.example` defines canonical `DATABASE_URL`, `REDIS_URL`, Celery and `STORAGE_*` variables. W1 runtime storage is frozen as `STORAGE_BACKEND=filesystem`; MinIO remains a provisioned S3-compatible dependency for later migration. |
| 6. Healthchecks | Done for provisioned services | PostgreSQL, Redis and MinIO are healthchecked. Backend/Worker checks are deferred with their containers. |
| 7. Local developer workflow | Done | `infra/README.md` documents start, status, logs, stop, reset, endpoints and the destructive-volume warning. |
| 8. CI foundation | Partial | Workflow `.github/workflows/backend-and-infra.yml` runs Backend storage tests and infrastructure smoke/contract tests. A successful GitHub Actions run/link is pending the first push and PR. |
| 9. Security baseline | Done for local baseline | `.env` and local data are ignored, `.env.example` contains placeholders only, MinIO bucket is private and bootstrap/smoke commands do not print credentials. Production secret management is explicitly out of W1 scope. |
| 10. Ownership boundary | Done | No FastAPI business endpoint, Worker logic, storage adapter rewrite, repository/business persistence, OCR or KIE implementation was added. |

## Definition of Done comparison

Completed locally:

- [x] Docker Compose configuration validates and starts the provisioned infrastructure.
- [x] PostgreSQL, Redis and MinIO become healthy.
- [x] PostgreSQL, Redis and MinIO use persistent named volumes.
- [x] Shared environment variables and `.env.example` are documented.
- [x] No real secret was added; MinIO bootstrap creates a private bucket.
- [x] Infrastructure services resolve through Compose service names.
- [x] Local setup, health checks and reset instructions are documented.
- [x] CI foundation is present.
- [x] No Backend-1/Backend-2 implementation was duplicated.
- [x] Local smoke evidence passed: persistence checks, 31 Backend storage tests and the full contract suite.

Still required before marking the whole attached DevOps task fully Done:

- [ ] Add runnable Backend API and Worker container definitions once their owners provide entrypoints, then prove they resolve `postgres`, `redis` and `minio` by service name.
- [ ] Push this branch, open a PR and attach the successful GitHub Actions workflow link/log as reproducibility evidence.

## Local evidence command

```bash
cp .env.example .env
PYTHON_BIN=.venv/bin/python ./infra/scripts/smoke-test.sh
```

The command passed locally on 2026-08-14. It validates Compose, health,
private-bucket bootstrap, internal DNS, volume persistence, 31 Backend storage
tests and the shared contract suite.
