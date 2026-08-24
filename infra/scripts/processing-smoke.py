"""Real compose smoke: upload a receipt and wait for PostgreSQL NEEDS_REVIEW."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
import psycopg


image_path = Path(os.environ["SMOKE_RECEIPT_IMAGE"])
base_url = os.getenv("SMOKE_BACKEND_URL", "http://localhost:8000")
database_url = os.environ["DATABASE_URL"]

with image_path.open("rb") as image:
    response = httpx.post(
        f"{base_url}/api/v1/receipts",
        files={"file": (image_path.name, image, "image/jpeg")},
        timeout=30,
    )
response.raise_for_status()
receipt_id = response.json()["receipt_id"]

deadline = time.monotonic() + int(os.getenv("SMOKE_TIMEOUT_SECONDS", "300"))
while time.monotonic() < deadline:
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            "SELECT status, latest_ocr_run_id, latest_kie_run_id "
            "FROM receipts WHERE receipt_id = %s",
            (receipt_id,),
        ).fetchone()
    if row and row[0] == "NEEDS_REVIEW" and row[1] and row[2]:
        print(f"PASS receipt_id={receipt_id} status=NEEDS_REVIEW")
        raise SystemExit(0)
    if row and row[0] == "FAILED":
        print(f"FAIL receipt_id={receipt_id} status=FAILED", file=sys.stderr)
        raise SystemExit(1)
    time.sleep(2)

print(f"FAIL timed out waiting for receipt_id={receipt_id}", file=sys.stderr)
raise SystemExit(1)
