# Implementation notes — DevOps Tasks 2 and 9

Date: 2026-08-14

## Outcome

Task 2 now has one canonical environment contract, and Task 9 runs both the
Backend receipt-image storage tests and the existing shared contract suite.
The local infrastructure smoke test still verifies PostgreSQL, Redis, MinIO,
service-name DNS, private bucket bootstrap and named-volume persistence.

## What changed

### Task 2 — shared environment

- Kept `DATABASE_URL` as the only database runtime source of truth for Backend
  and Worker. `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` are only
  PostgreSQL-container bootstrap inputs.
- Froze the W1 application adapter as `STORAGE_BACKEND=filesystem`, matching
  the Backend config, which accepts only `filesystem` or `s3`.
- Kept all project-level storage names under `STORAGE_*`; no `S3_*` aliases or
  duplicate `MINIO_ROOT_*` values exist in `.env.example`.
- Docker Compose maps `STORAGE_ACCESS_KEY` and `STORAGE_SECRET_KEY` to MinIO's
  required vendor names inside the MinIO container.
- Added `KIE_TIMEOUT_SECONDS` next to `OCR_TIMEOUT_SECONDS`.
- Kept local placeholder credentials only. No production secret was added.

### Task 9 — tests and CI

- Updated the test plan to acknowledge and run the Backend storage tests now
  present under `backend/tests`.
- Extended `infra/scripts/smoke-test.sh` to run Backend storage tests followed
  by the shared JSON/OpenAPI contract suite.
- Added a dedicated GitHub Actions job for Backend storage tests.
- Added a separate infrastructure smoke job with failure logs and guaranteed
  container/volume cleanup on the ephemeral CI runner.
- Added `backend/**` to workflow path filters so storage changes trigger CI.
- Disabled automatic loading of globally installed pytest plugins so the test
  result depends only on project-declared test dependencies.

## Deliberately not done

- Backend API and Worker containers were not added. The repository still does
  not provide the FastAPI/Celery entrypoints required for meaningful runtime
  containers; adding placeholder processes would report false health.
- Runtime storage was not switched to MinIO. MinIO is provisioned, health
  checked and bootstrapped as private infrastructure, while the team-approved
  W1 application adapter remains `filesystem`.
- No Backend storage factory, business repository, receipt lifecycle, OCR/KIE
  implementation or database migration was added. Those belong to Backend-1,
  Backend-2, OCR or KIE owners.
- The empty `infra/docker/backend.Dockerfile` was not implemented because that
  belongs to the later Backend/Worker container integration task.
- Existing broad `results/` ignore behavior and host-port exposure were not
  changed because this request was limited to Tasks 2 and 9. They should be
  reviewed separately before the final PR.

## Trade-offs and operational notes

- MinIO uses the same local placeholder storage credentials for root bootstrap
  and smoke testing. This keeps W1 setup simple; production must use separate,
  least-privilege application credentials and secret injection.
- The filesystem adapter is simplest for W1. When Backend and Worker become
  separate containers, they must mount the same receipt-image volume or switch
  together to `STORAGE_BACKEND=s3` for MinIO access.
- The smoke test intentionally writes one marker to PostgreSQL, Redis and
  MinIO, then recreates containers to prove persistence. Local runs leave the
  stack and markers in place for inspection; `docker compose down -v` removes
  them irreversibly.
- CI uses `docker compose down -v --remove-orphans` because GitHub runners are
  ephemeral and should not retain test volumes.
- The feature branch was rebased onto the current `main` during this work. The
  `.env.example` stash conflict was resolved by preserving Backend's storage
  variables and DevOps's PostgreSQL/bootstrap additions without duplication.

## Validation commands

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-contracts.txt
.venv/bin/python -m pip install -e "./backend[test]"
PYTHON_BIN=.venv/bin/python ./infra/scripts/smoke-test.sh
docker compose ps -a
git diff --check
```

## Validation result

Validated locally on 2026-08-14 with Python 3.12.13 and Docker Compose:

- Compose configuration, shell syntax and GitHub Actions YAML are valid.
- PostgreSQL, Redis and MinIO reached `healthy`; `minio-init` exited with 0.
- `postgres`, `redis` and `minio` resolved by Compose service name.
- PostgreSQL, Redis and MinIO markers survived forced container recreation.
- The MinIO bucket existed and remained private.
- All 31 Backend storage tests passed.
- The complete shared OpenAPI/JSON Schema contract suite passed, including 9
  positive and 23 negative schema cases.
- `.env` and `.data/` are ignored, while `.env.example` remains tracked.
