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
p.add_argument(
    "--expected-json",
    type=Path,
    help="Synthetic fixture expectation: header, line_count, tax_count",
)
p.add_argument(
    "--review-json",
    type=Path,
    help="Explicit synthetic reference values for human corrections; never machine accuracy evidence",
)
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
    machine_header = {
        field: cell["effective_value"] for field, cell in detail["fields"].items()
    }
    if a.expected_json:
        expected = json.loads(a.expected_json.read_text(encoding="utf-8"))
        assert machine_header == expected["header"], (
            "Machine headers differ from the synthetic fixture"
        )
        assert len(detail["line_items"]) == expected["line_count"]
        assert len(detail["tax_breakdown"]) == expected["tax_count"]
    response = client.get(f"/api/v2/receipts/{rid}/evidence")
    response.raise_for_status()
    document = response.json()
    engines = (
        [page["evidence"]["engine"] for page in document["pages"]]
        if document["schema_version"] == "document-2.0"
        else [document["engine"]]
    )
    reference = (
        json.loads(a.review_json.read_text(encoding="utf-8")) if a.review_json else {}
    )
    sections = {
        "fields": "header",
        "line-items": "line_items",
        "tax-groups": "tax_breakdown",
    }
    for key, rows in (
        ("line_items", detail["line_items"]),
        ("tax_breakdown", detail["tax_breakdown"]),
    ):
        if key in reference:
            assert len(reference[key]) == len(rows), (
                "Reference and machine row counts differ"
            )
    # Smoke explicitly confirms each proposed status/value as the demo reviewer.
    for section, rows in [
        ("fields", [("", detail["fields"])]),
        ("line-items", [(r["line_id"], r) for r in detail["line_items"]]),
        ("tax-groups", [(r["tax_id"], r) for r in detail["tax_breakdown"]]),
    ]:
        for row_index, (row_id, row) in enumerate(rows):
            reviewed = reference.get(
                sections[section], {} if section == "fields" else []
            )
            reviewed = (
                reviewed
                if section == "fields"
                else (reviewed[row_index] if reviewed else {})
            )
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
                        "value": reviewed.get(field, cell["effective_value"]),
                        "status": (
                            "PRESENT" if reviewed[field] is not None else "NOT_PRESENT"
                        )
                        if field in reviewed
                        else cell["effective_status"],
                    },
                )
                response.raise_for_status()
                detail = response.json()
    response = client.post(
        f"/api/v2/receipts/{rid}/verify", json={"expected_version": detail["version"]}
    )
    response.raise_for_status()
    detail = response.json()
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
        machine_header=machine_header,
        reviewed_header={
            field: cell["effective_value"] for field, cell in detail["fields"].items()
        },
        human_review="provided-synthetic-reference"
        if a.review_json
        else "explicitly-confirmed-machine-values",
        machine_version=machine_version,
        engines=engines,
        line_count=len(detail["line_items"]),
        tax_count=len(detail["tax_breakdown"]),
        status=detail["status"],
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
