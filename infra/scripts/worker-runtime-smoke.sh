#!/usr/bin/env bash

set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="$repo_root/docker-compose.yml"
env_file="${ENV_FILE:-$repo_root/.env}"
python_bin="${PYTHON_BIN:-python3}"

if [[ ! -f "$env_file" ]]; then
  echo "Missing $env_file. Run: cp .env.example .env" >&2
  exit 1
fi

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

configured_platform="$(compose config --format json | "$python_bin" -c '
import json
import sys

print(json.load(sys.stdin)["services"]["worker"].get("platform", ""))
')"
case "$configured_platform" in
  linux/amd64 | linux/amd64/*) expected_machine="x86_64" ;;
  linux/arm64 | linux/arm64/* | linux/aarch64 | linux/aarch64/*)
    expected_machine="aarch64"
    ;;
  *) expected_machine="" ;;
esac

actual_machine="$(compose exec -T worker uname -m)"
if [[ -n "$expected_machine" && "$actual_machine" != "$expected_machine" ]]; then
  echo "Worker architecture '$actual_machine' does not match '$expected_machine'." >&2
  exit 1
fi

compose exec -T worker python - <<'PY'
from importlib.metadata import version
import os
import warnings

warnings.filterwarnings("ignore", message="No ccache found.*")

python_path = os.environ.get("PYTHONPATH", "").split(":")
if "/app" not in python_path:
    raise SystemExit("Worker PYTHONPATH does not contain /app.")

import paddle

expected_version = "3.0.0"
actual_version = version("paddlepaddle")
if actual_version != expected_version:
    raise SystemExit(
        f"paddlepaddle={actual_version}; expected {expected_version}."
    )

paddle.utils.run_check()
print(
    "PASS worker runtime "
    f"paddlepaddle={actual_version} "
    "PYTHONPATH=/app"
)
PY

echo "PASS worker architecture platform=$configured_platform machine=$actual_machine"
