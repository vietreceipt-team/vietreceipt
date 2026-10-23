"""Manifest-driven HTTP experiment runner; machine artifacts never contain corrections."""

import argparse
import csv
import hashlib
import io
import json
import mimetypes
import platform
import re
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def dump(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(response):
    response.raise_for_status()
    return response.json()


def load_manifest(path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not all(manifest.get(key) for key in ("dataset", "version", "split", "samples")):
        raise ValueError(
            "Manifest requires dataset, version, split and nonempty samples"
        )
    ids = [sample["id"] for sample in manifest["samples"]]
    if len(set(ids)) != len(ids) or any(
        not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", sid) for sid in ids
    ):
        raise ValueError("Sample IDs must be unique, safe path components")
    return manifest


def review_synthetic(client, rid, detail, reference):
    """Explicit test reviewer only on records uploaded by this run, never user records."""
    changes = []
    for section, rows, ref_key in (
        ("fields", [("", detail["fields"])], "header"),
        ("line-items", [(r["line_id"], r) for r in detail["line_items"]], "line_items"),
        (
            "tax-groups",
            [(r["tax_id"], r) for r in detail["tax_breakdown"]],
            "tax_breakdown",
        ),
    ):
        ref = reference.get(ref_key, {} if section == "fields" else [])
        if section != "fields" and ref and len(ref) != len(rows):
            raise ValueError("Synthetic review row count differs from machine rows")
        for index, (row_id, row) in enumerate(rows):
            values = ref if section == "fields" else (ref[index] if ref else {})
            for field, cell in row.items():
                if not isinstance(cell, dict):
                    continue
                if field not in values and not cell["effective_needs_review"]:
                    continue
                value = values.get(field, cell["effective_value"])
                status = (
                    ("PRESENT" if value is not None else "NOT_PRESENT")
                    if field in values
                    else cell["effective_status"]
                )
                body = dict(
                    expected_version=detail["version"], value=value, status=status
                )
                route = (
                    f"/api/v2/receipts/{rid}/{section}/"
                    + (row_id + "/" if row_id else "")
                    + field
                    + "/correction"
                )
                detail = checked(client.patch(route, json=body))
                changes.append(
                    dict(
                        section=section,
                        row_id=row_id,
                        field=field,
                        value=value,
                        status=status,
                    )
                )
    detail = checked(
        client.post(
            f"/api/v2/receipts/{rid}/verify",
            json={"expected_version": detail["version"]},
        )
    )
    if detail["status"] != "VERIFIED":
        raise ValueError("Review did not reach VERIFIED")
    return detail, changes


def verify_exports(client, rid, folder, reference):
    exports = {}
    expected = reference.get("header", {})
    for fmt in ("json", "csv", "xlsx"):
        response = client.get(f"/api/v2/receipts/{rid}/export", params={"format": fmt})
        response.raise_for_status()
        if not response.content:
            raise ValueError("Empty export")
        extension = "zip" if fmt == "csv" else fmt
        (folder / ("export." + extension)).write_bytes(response.content)
        if fmt == "json":
            if any(
                response.json()["header"][key] != val for key, val in expected.items()
            ):
                raise ValueError("JSON export lost reviewed values")
        elif fmt == "csv":
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                rows = list(
                    csv.DictReader(
                        io.StringIO(
                            archive.read("invoice_headers.csv").decode("utf-8-sig")
                        )
                    )
                )
                if len(rows) != 1 or any(
                    rows[0][key] != ("" if val is None else str(val))
                    for key, val in expected.items()
                ):
                    raise ValueError("CSV export lost reviewed values")
        else:
            from openpyxl import load_workbook

            book = load_workbook(io.BytesIO(response.content), read_only=True)
            try:
                rows = list(book["Invoices"].values)
                values = dict(zip(rows[0], rows[1]))
                if any(values[key] != val for key, val in expected.items()):
                    raise ValueError("XLSX export lost reviewed values")
            finally:
                book.close()
        exports[fmt] = dict(
            bytes=len(response.content), sha256=digest(response.content)
        )
    return exports


def run(
    manifest_path,
    output,
    *,
    url,
    timeout=300,
    poll_interval=1,
    review=False,
    mode="real",
    client=None,
):
    if timeout <= 0 or poll_interval < 0:
        raise ValueError("Timeout must be positive and polling interval nonnegative")
    manifest_path = manifest_path.resolve()
    manifest = load_manifest(manifest_path)
    if review and not (
        manifest.get("synthetic") is True
        and manifest["split"] in ("development", "demo")
    ):
        raise ValueError(
            "Automated review requires an explicitly synthetic development/demo manifest"
        )
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "manifest.json", manifest)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True
    )
    dump(
        output / "run.json",
        dict(
            schema_version="backend-evaluation-1.0",
            started_at=datetime.now(timezone.utc).isoformat(),
            manifest_sha256=digest(manifest_path.read_bytes()),
            runner_commit=commit.stdout.strip() or None,
            runner_dirty=bool(dirty.stdout.strip()),
            runner_python=platform.python_version(),
            mode=mode,
            timeout_seconds=timeout,
            poll_interval_seconds=poll_interval,
            synthetic_review=review,
            timing_policy="Client upload and queue+processing wall time; actual worker stage durations/config/commit are in machine/attempts. Includes subprocess startup and model load; not a warm inference benchmark.",
            metric_policy="Raw machine artifacts only; reviewed exports are workflow evidence, never AI accuracy. No accuracy score is claimed.",
        ),
    )
    own_client = client is None
    client = client or httpx.Client(base_url=url, timeout=30)
    rows = []
    try:
        for sample in manifest["samples"]:
            folder = output / sample["id"]
            folder.mkdir()
            (folder / "machine").mkdir()
            row = dict(
                id=sample["id"],
                condition=sample.get("condition"),
                status="failed",
                receipt_id=None,
                input_sha256=None,
                upload_ms=None,
                processing_wall_ms=None,
                total_ms=None,
                error=None,
            )
            started = time.perf_counter()
            try:
                data = (manifest_path.parent / sample["path"]).read_bytes()
                row["input_sha256"] = digest(data)
                if sample.get("sha256") and sample["sha256"] != row["input_sha256"]:
                    raise ValueError("Source checksum differs from manifest")
                mime = (
                    sample.get("content_type")
                    or mimetypes.guess_type(sample["path"])[0]
                )
                source = client.post(
                    "/api/v2/receipts",
                    files={"file": (Path(sample["path"]).name, data, mime)},
                )
                detail = checked(source)
                rid = row["receipt_id"] = detail["receipt_id"]
                row["upload_ms"] = round((time.perf_counter() - started) * 1000, 3)
                dump(folder / "upload.json", detail)
                processing_started = time.perf_counter()
                deadline = time.monotonic() + timeout
                while detail["status"] in ("UPLOADED", "PROCESSING"):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Processing exceeded experiment deadline")
                    time.sleep(poll_interval)
                    detail = checked(client.get(f"/api/v2/receipts/{rid}"))
                row["processing_wall_ms"] = round(
                    (time.perf_counter() - processing_started) * 1000, 3
                )
                dump(folder / "processing.json", detail)
                snapshot = checked(
                    client.get(f"/api/v2/receipts/{rid}/machine-results")
                )
                dump(folder / "machine" / "snapshot.json", snapshot)
                for machine in snapshot["runs"]:
                    dump(
                        folder
                        / "machine"
                        / (machine["kind"].lower() + "-" + machine["run_id"] + ".json"),
                        machine["payload"],
                    )
                if detail["status"] != "NEEDS_REVIEW":
                    raise ValueError(
                        "Processing failed: "
                        + json.dumps(detail.get("processing_error"))
                    )
                successful = [
                    a
                    for a in snapshot["attempts"]
                    if a["status"] == "SUCCEEDED"
                    and a["kie_run_id"] == detail["latest_kie_run_id"]
                ]
                if len(successful) != 1 or not successful[0].get("provenance"):
                    raise ValueError("Missing worker provenance for selected KIE run")
                providers = successful[0]["provenance"]["config"]["providers"]
                if mode == "real" and (
                    successful[0]["provenance"]["config"].get("callables")
                    != {
                        "reader": "backend.app.v2.providers:configured_reader",
                        "kie": "backend.app.v2.providers:configured_kie",
                    }
                    or providers
                    != {
                        "V2_DOCUMENT_READER_CALLABLE": "ai.document_reader.backend:read_document",
                        "V2_KIE_CALLABLE": "ai.kie.v2:extract_invoice",
                    }
                ):
                    raise ValueError(
                        "Real evaluation requires the canonical TV3/TV4 providers; use --mode test for test doubles"
                    )
                if review:
                    review_folder = folder / "reviewed"
                    review_folder.mkdir()
                    reference = sample.get("review", {})
                    detail, changes = review_synthetic(client, rid, detail, reference)
                    dump(review_folder / "detail.json", detail)
                    dump(review_folder / "corrections.json", changes)
                    row["exports"] = verify_exports(
                        client, rid, review_folder, reference
                    )
                    after = checked(
                        client.get(f"/api/v2/receipts/{rid}/machine-results")
                    )
                    if snapshot != after:
                        raise ValueError("Machine artifacts changed after review")
                row["status"] = "verified" if review else "needs_review"
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                httpx.HTTPError,
                TimeoutError,
                zipfile.BadZipFile,
            ) as exc:
                row["error"] = dict(type=type(exc).__name__, message=str(exc))
                if row["receipt_id"]:
                    try:
                        dump(
                            folder / "machine" / "snapshot.json",
                            checked(
                                client.get(
                                    f"/api/v2/receipts/{row['receipt_id']}/machine-results"
                                )
                            ),
                        )
                    except httpx.HTTPError:
                        pass
            finally:
                row["total_ms"] = round((time.perf_counter() - started) * 1000, 3)
                dump(folder / "result.json", row)
                rows.append(row)
                dump(
                    output / "summary.json",
                    dict(
                        dataset=manifest["dataset"],
                        samples=rows,
                        complete=len(rows) == len(manifest["samples"]),
                        failed=sum(r["status"] == "failed" for r in rows),
                    ),
                )
                print(f"{row['id']}: {row['status']}", flush=True)
    finally:
        if own_client:
            client.close()
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--poll-interval", type=float, default=1)
    parser.add_argument("--mode", choices=("real", "test"), default="real")
    parser.add_argument("--review-synthetic", action="store_true")
    args = parser.parse_args()
    rows = run(
        args.manifest,
        args.output,
        url=args.url,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        review=args.review_synthetic,
        mode=args.mode,
    )
    if any(row["status"] == "failed" for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
