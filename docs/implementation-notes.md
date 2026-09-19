> **LEGACY v1 NOTICE (19/09/2026):** This file belongs to the former five-field Week-1/2/3 plan. Do not use it as a current requirement. See `README.md`, `docs/project-plan.md` and `docs/migration-status.md`.

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

## Update — 2026-08-17: Backend, Worker and Frontend containers

`origin/main` merged the Week-2 Core Receipt and HITL API (#19) after this
branch diverged, so `backend/app/main.py` (a real FastAPI entrypoint) did not
exist here until now. This update merges `origin/main` into the branch and
adds the three containers that were previously deliberately deferred.

### What changed

- Merged `origin/main` (merge commit, no rebase/force-push) to bring in
  `backend/app/main.py` and the full API package.
- Replaced the placeholder `infra/docker/backend.Dockerfile` with a real
  image: installs `backend/requirements.txt`, runs
  `uvicorn backend.app.main:app`. DevOps only wires the container; the app
  code is Backend-1's.
- Added `infra/docker/worker.Dockerfile` and
  `infra/docker/worker/celery_app.py` — a Celery app with **no registered
  task**, only proving the worker can reach the Redis broker. Task/business
  logic remains Backend-1/Backend-2 scope.
- Added `infra/docker/frontend.Dockerfile` running `next dev` for local
  Compose use (not a production image).
- Added `backend`, `worker` and `frontend` services to `docker-compose.yml`,
  each on `vietreceipt_internal`, each consuming the existing canonical
  `DATABASE_URL` / `REDIS_URL` / `CELERY_*` / `STORAGE_*` variables. `backend`
  and `worker` have Docker healthchecks; `frontend` does not (dev server has
  no cheap health endpoint), so the smoke test checks it at the HTTP level
  instead.
- Added `BACKEND_PORT` / `FRONTEND_PORT` overrides to `.env.example`.
- Extended `infra/scripts/smoke-test.sh` to wait for `backend`/`worker`
  health, assert `backend` resolves `postgres`/`redis`/`minio` by service
  name (the concrete proof for DoD item 9), and check `backend` and
  `frontend` respond over HTTP.
- Fixed the CI install step: the merged `backend/tests` now includes
  FastAPI route tests using `TestClient`, which requires `httpx2` (this
  project's pinned HTTP client, declared in `backend/requirements-dev.txt`)
  — not just the `pyproject.toml` `[test]` extra (`pytest` only). Both CI
  jobs now install
  `pip install -e "./backend[test]" -r backend/requirements-dev.txt`.

### Deliberately still not done

- Worker still has zero receipt-processing tasks — that is Backend-1/
  Backend-2 scope, not DevOps.
- Frontend is not wired to call the Backend API (no `NEXT_PUBLIC_API_*`
  variable exists in the frontend code yet); containerizing it does not
  change that.
- `backend`'s `service_registry` is `None` by default (`create_app()`), so
  most `/api/v1/*` endpoints will 500 until Backend wires real
  persistence/repositories. The healthcheck deliberately targets
  `/openapi.json`, which does not depend on `service_registry`.

### Validation — 2026-08-17

- `docker compose build backend worker frontend` succeeded.
- `docker compose up -d` brought up all 6 services; `postgres`, `redis`,
  `minio`, `backend` and `worker` reached `healthy`; `minio-init` exited 0.
- `GET http://localhost:8000/openapi.json` returned the real VietReceipt
  OpenAPI document.
- `GET http://localhost:3000` returned the Next.js app shell.
- `backend` container resolved `postgres`, `redis` and `minio` by service
  name via `getent hosts`.
- `docker compose exec backend pip install -e "./backend[test]" -r
  backend/requirements-dev.txt && pytest backend/tests` — 122 passed (31
  storage tests + 91 API/domain tests from the Week-2 merge).

## Update — 2026-08-17 (cont.): Backend entrypoint contract confirmed

Backend owner confirmed the FastAPI entrypoint contract in writing:

- Module path from the repository root: `backend.app.main:app`.
- Run command: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port
  8000`.
- Dependencies: `fastapi==0.141.1`, `pydantic==2.13.4`,
  `pydantic-settings==2.15.0`, `python-multipart==0.0.32`,
  `uvicorn[standard]==0.52.3` (all in `backend/requirements.txt`).
- No `/healthz` or `/readyz` endpoint exists yet in PR #19; Backend
  explicitly advises against configuring a Compose healthcheck against an
  endpoint that does not exist.

`infra/docker/backend.Dockerfile` already matched this contract in
substance (same module path, host, port, dependency source) and was
adjusted to use the exact `python -m uvicorn ...` invocation form for
one-to-one traceability against the confirmed command.

The `backend` Compose healthcheck intentionally targets `/openapi.json`
instead — a route FastAPI serves out of the box, independent of
`app.state.service_registry` — as an interim liveness probe. **When Backend
ships `/healthz` (and optionally `/readyz`), the healthcheck in
`docker-compose.yml` should switch to it**; this is not done yet because
the endpoint does not exist.

Backend owner also confirmed the `STORAGE_*` naming (vs. the `S3_*` names
in the original task text) is correct and should stay as-is; no rename is
needed.

### Worker: skeleton is the W1 deliverable, not a placeholder debt

The Celery module path, worker command and Redis/Celery dependencies were
confirmed **not yet decided** by Backend/Worker owners as of PR #19 — no
concrete Celery application exists in `backend/` yet. The `worker` service
added in this branch (`infra/docker/worker/celery_app.py`,
`infra/docker/worker.Dockerfile`) is a **DevOps-owned infra skeleton**: it
has zero registered tasks and its own separately pinned
`celery[redis]==5.4.0`. Its healthcheck already uses the method the Backend
owner suggested (`celery -A <app> inspect ping`).

This is a materially different situation from Backend, which was a real
"integrate the entrypoint that now exists" task. **For Worker, the skeleton
itself is the W1 deliverable** — the task asks for a "Worker
container/skeleton", and that is what shipped. It is not a blocker for
closing this task.

Replacing it with a real application worker is follow-up work under **Issue
#21 (Backend processing integration)**, owned by Backend-1, because the
real processing path — `enqueue receipt_id → worker claim → PROCESSING →
OCR → KIE → NEEDS_REVIEW` — is receipt-processing business semantics.

Ownership split for the worker, to keep this unambiguous:

- **DevOps** owns the worker *container and process*: Dockerfile, broker
  configuration, networking, healthcheck, logs/runtime visibility.
- **Backend-1** owns the worker *handler and orchestration*:
  `ProcessingScheduler` semantics, application queue adapter, processing
  job payload, receipt state transitions, retry/idempotency and business
  failure semantics.

When Backend-1 commits a concrete Celery app, DevOps points
`infra/docker/worker.Dockerfile` at their module path and retires the
DevOps-owned `celery_app.py` skeleton and
`infra/docker/worker/requirements.txt` pin in favor of Backend's own.
