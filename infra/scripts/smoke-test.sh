#!/usr/bin/env bash

set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="$repo_root/docker-compose.yml"
env_file="${ENV_FILE:-$repo_root/.env}"
marker="vietreceipt-smoke-marker"
python_bin="${PYTHON_BIN:-python3}"

if [[ ! -f "$env_file" ]]; then
  echo "Missing $env_file. Run: cp .env.example .env" >&2
  exit 1
fi

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

wait_for_healthy() {
  local service="$1"
  local container_id status

  container_id="$(compose ps -q "$service")"
  if [[ -z "$container_id" ]]; then
    echo "Service '$service' has no running container." >&2
    return 1
  fi

  for _ in {1..45}; do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")"
    if [[ "$status" == "healthy" ]]; then
      echo "[ok] $service is healthy"
      return 0
    fi
    if [[ "$status" == "exited" || "$status" == "dead" ]]; then
      echo "Service '$service' stopped before becoming healthy." >&2
      compose logs "$service" >&2
      return 1
    fi
    sleep 2
  done

  echo "Timed out waiting for '$service' to become healthy." >&2
  compose logs "$service" >&2
  return 1
}

wait_for_init() {
  local container_id state exit_code

  for _ in {1..45}; do
    container_id="$(compose ps -a -q minio-init)"
    if [[ -n "$container_id" ]]; then
      state="$(docker inspect --format '{{.State.Status}}' "$container_id")"
      if [[ "$state" == "exited" ]]; then
        exit_code="$(docker inspect --format '{{.State.ExitCode}}' "$container_id")"
        if [[ "$exit_code" == "0" ]]; then
          echo "[ok] minio-init exited successfully"
          return 0
        fi
        compose logs minio-init >&2
        return 1
      fi
    fi
    sleep 2
  done

  echo "Timed out waiting for minio-init." >&2
  compose logs minio-init >&2
  return 1
}

verify_bucket() {
  local policy

  compose run --rm --no-deps --entrypoint /bin/sh minio-init -c '
    set -eu
    mc alias set verify "$STORAGE_ENDPOINT" "$STORAGE_ACCESS_KEY" "$STORAGE_SECRET_KEY" >/dev/null
    mc stat "verify/$STORAGE_BUCKET" >/dev/null
  '
  policy="$(compose run --rm --no-deps --entrypoint /bin/sh minio-init -c '
    set -eu
    mc alias set verify "$STORAGE_ENDPOINT" "$STORAGE_ACCESS_KEY" "$STORAGE_SECRET_KEY" >/dev/null
    mc anonymous get "verify/$STORAGE_BUCKET"
  ')"
  grep -qi private <<<"$policy"
  echo "[ok] MinIO bucket exists and is private"
}

write_persistence_markers() {
  compose exec -T postgres sh -c \
    'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<SQL
CREATE TABLE IF NOT EXISTS infra_smoke_test (
  marker text PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO infra_smoke_test(marker) VALUES ('$marker')
ON CONFLICT (marker) DO NOTHING;
SQL

  compose exec -T redis redis-cli SET infra_smoke_test "$marker" >/dev/null
  compose run --rm --no-deps --entrypoint /bin/sh minio-init -c '
    set -eu
    mc alias set verify "$STORAGE_ENDPOINT" "$STORAGE_ACCESS_KEY" "$STORAGE_SECRET_KEY" >/dev/null
    printf "%s" "vietreceipt-smoke-marker" | mc pipe "verify/$STORAGE_BUCKET/.smoke/persistence"
  ' >/dev/null
}

verify_persistence_markers() {
  compose exec -T postgres sh -c \
    'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT marker FROM infra_smoke_test WHERE marker = '\''vietreceipt-smoke-marker'\''"' \
    | grep -Fxq "$marker"
  compose exec -T redis redis-cli GET infra_smoke_test | grep -Fxq "$marker"
  compose run --rm --no-deps --entrypoint /bin/sh minio-init -c '
    set -eu
    mc alias set verify "$STORAGE_ENDPOINT" "$STORAGE_ACCESS_KEY" "$STORAGE_SECRET_KEY" >/dev/null
    mc cat "verify/$STORAGE_BUCKET/.smoke/persistence"
  ' | grep -Fq "$marker"
  echo "[ok] PostgreSQL, Redis and MinIO data survived container recreation"
}

cd "$repo_root"

echo "[1/8] Validate Compose configuration"
compose config --quiet

echo "[2/8] Start infrastructure"
compose up -d

echo "[3/8] Check service health and MinIO bootstrap"
wait_for_healthy postgres
wait_for_healthy redis
wait_for_healthy minio
wait_for_init
verify_bucket

echo "[4/8] Check service-name DNS on the internal network"
compose exec -T postgres getent hosts postgres redis minio >/dev/null
echo "[ok] postgres, redis and minio resolve by service name"

echo "[5/8] Write persistence markers"
write_persistence_markers

echo "[6/8] Recreate containers and verify named volumes"
compose up -d --force-recreate
wait_for_healthy postgres
wait_for_healthy redis
wait_for_healthy minio
wait_for_init
verify_persistence_markers

echo "[7/8] Run Backend storage tests"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$python_bin" -m pytest backend/tests

echo "[8/8] Run repository contract tests"
"$python_bin" tests/contracts/run_contract_tests.py

echo "All infrastructure smoke checks passed."
