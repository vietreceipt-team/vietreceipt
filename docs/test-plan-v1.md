# VietReceipt local infrastructure test plan v1

## Scope

This plan verifies the reproducible local infrastructure used by Backend and
Worker: PostgreSQL, Redis, MinIO, Docker networking, MinIO bucket bootstrap and
named-volume persistence. It intentionally does not test Backend business
logic, OCR accuracy or KIE extraction quality.

## Preconditions

- Docker Engine and Docker Compose are installed.
- Python 3.12 is available.
- `.env` was created from `.env.example` and contains local-only credentials.
- Ports 5432, 6379, 9000 and 9001 are available, or their `*_PORT` overrides
  are set in `.env`.

## Automated smoke test

Run from the repository root:

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-contracts.txt
.venv/bin/python -m pip install -e "./backend[test]" -r backend/requirements-dev.txt
PYTHON_BIN=.venv/bin/python ./infra/scripts/smoke-test.sh
```

The script is repeatable. It leaves the infrastructure running and retains its
test records so that persistence can be checked again on the next run.

| ID | Check | Type | Expected result |
| --- | --- | --- | --- |
| INF-01 | `docker compose config --quiet` | Static/config | Compose is valid. |
| INF-02 | PostgreSQL readiness with `pg_isready` | Integration | Service becomes `healthy`. |
| INF-03 | Redis readiness with `redis-cli ping` | Integration | Service becomes `healthy`. |
| INF-04 | MinIO live endpoint | Integration | Service becomes `healthy`. |
| INF-05 | `minio-init` completion | Integration | One-shot container exits with code 0. |
| INF-06 | Bucket bootstrap and access policy | Security/integration | `vietreceipt` exists and is private. |
| INF-07 | Compose service-name resolution | Network | `postgres`, `redis`, and `minio` resolve inside the network. |
| INF-08 | Forced container recreation | Persistence | PostgreSQL row, Redis key and MinIO object remain. |
| INF-09 | Backend receipt-image storage adapters/configuration | Unit | `backend/tests` passes. |
| INF-10 | Shared JSON contracts | Contract | Existing contract suite passes. |
| INF-11 | Secret/local-data exclusion | Static/security | `.env` and `.data/` do not appear in `git status`; `.env.example` remains tracked. |

## Manual checks

1. Run `docker compose ps -a`; PostgreSQL, Redis and MinIO must be `healthy`,
   while `minio-init` must be `Exited (0)`.
2. Run `git status --short --ignored`; `.env` and `.data/` must be ignored and
   `.env.example` must not be ignored.
3. Confirm `STORAGE_BACKEND=filesystem`; MinIO is provisioned and tested, but
   is not the W1 application storage adapter.
4. Run the Backend storage suite independently when diagnosing unit failures:
   `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest backend/tests`.

## Failure diagnostics

- `docker compose logs postgres redis minio minio-init` shows startup and
  bootstrap failures.
- `docker compose config` shows the fully resolved configuration; inspect it
  locally and never paste secrets into an issue.
- A port conflict can be resolved with `POSTGRES_PORT`, `REDIS_PORT`,
  `MINIO_API_PORT`, or `MINIO_CONSOLE_PORT` in `.env`.
- To retry without deleting data, use `docker compose down` followed by
  `docker compose up -d`.

## Destructive reset

```bash
docker compose down -v
```

This permanently deletes all local PostgreSQL, Redis and MinIO volume data.
