"""HTTP smoke through an already running API/Redis/worker; never selects fake providers."""

import argparse
import json
import mimetypes
import time
from pathlib import Path

import httpx

p = argparse.ArgumentParser()
p.add_argument("source", type=Path)
p.add_argument("--url", default="http://localhost:8000")
p.add_argument("--timeout", type=int, default=300)
p.add_argument("--database-url", help="Read-only query to capture attempt/run linkage")
p.add_argument(
    "--test-providers",
    action="store_true",
    help="Label evidence as backend-only; never real AI",
)
p.add_argument("--output", type=Path, default=Path("smoke-v2-evidence.json"))
a = p.parse_args()
with httpx.Client(base_url=a.url, timeout=30) as client:
    with a.source.open("rb") as source:
        response = client.post(
            "/api/v2/receipts",
            files={
                "file": (a.source.name, source, mimetypes.guess_type(a.source.name)[0])
            },
        )
    response.raise_for_status()
    detail = response.json()
    rid = detail["receipt_id"]
    start = time.monotonic()
    while detail["status"] in ("UPLOADED", "PROCESSING"):
        if time.monotonic() - start > a.timeout:
            raise RuntimeError(f"Processing timeout receipt_id={rid}")
        time.sleep(1)
        response = client.get(f"/api/v2/receipts/{rid}")
        response.raise_for_status()
        detail = response.json()
    if detail["status"] != "NEEDS_REVIEW":
        raise RuntimeError(
            f"Processing failed: {detail.get('processing_error')} receipt_id={rid}"
        )
    assert len(detail["fields"]) == 13
    machine_version = detail["version"]
    # Smoke explicitly confirms each proposed status/value as the demo reviewer.
    for section, rows in [
        ("fields", [("", detail["fields"])]),
        ("line-items", [(r["line_id"], r) for r in detail["line_items"]]),
        ("tax-groups", [(r["tax_id"], r) for r in detail["tax_breakdown"]]),
    ]:
        for row_id, row in rows:
            for field, cell in row.items():
                if not isinstance(cell, dict):
                    continue
                path = (
                    f"/api/v2/receipts/{rid}/{section}/"
                    + (row_id + "/" if row_id else "")
                    + field
                    + "/correction"
                )
                response = client.patch(
                    path,
                    json={
                        "expected_version": detail["version"],
                        "value": cell["effective_value"],
                        "status": cell["effective_status"],
                    },
                )
                response.raise_for_status()
                detail = response.json()
    response = client.post(
        f"/api/v2/receipts/{rid}/verify", json={"expected_version": detail["version"]}
    )
    response.raise_for_status()
    exports = {}
    for fmt in ("json", "csv", "xlsx"):
        response = client.get(f"/api/v2/receipts/{rid}/export", params={"format": fmt})
        response.raise_for_status()
        assert response.content
        exports[fmt] = len(response.content)
    evidence = dict(
        mode="backend-test-providers"
        if a.test_providers
        else "real-configured-providers",
        receipt_id=rid,
        ocr_run_id=detail["latest_ocr_run_id"],
        kie_run_id=detail["latest_kie_run_id"],
        field_count=13,
        line_count=len(detail["line_items"]),
        export_bytes=exports,
        elapsed_seconds=round(time.monotonic() - start, 3),
    )
    if a.database_url:
        from sqlalchemy import select

        from backend.app.v2.models import Attempt
        from backend.app.v2.runtime import database_engine

        with database_engine(a.database_url).connect() as conn:
            attempt = conn.execute(
                select(Attempt.attempt_id).where(
                    Attempt.receipt_id == rid, Attempt.status == "SUCCEEDED"
                )
            ).scalar_one()
            evidence["attempt_id"] = attempt
    a.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(json.dumps(evidence, ensure_ascii=False))
