"""Machine-only batch indexes and system metrics; never infer accuracy from review."""

import csv
import json
from collections import Counter


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def reports(output, manifest, rows):
    indexes = []
    table = []
    for row in rows:
        path = output / row["id"] / "machine/snapshot.json"
        snapshot = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        )
        error = row.get("error") or {}
        indexes.append(
            dict(
                sample_id=row["id"],
                input_sha256=row["input_sha256"],
                receipt_id=row["receipt_id"],
                processing_success=row["processing_success"],
                snapshot_path=f"{row['id']}/machine/snapshot.json"
                if snapshot
                else None,
                attempts=snapshot["attempts"] if snapshot else [],
                runs=snapshot["runs"] if snapshot else [],
            )
        )
        timings = {}
        if snapshot:
            attempts = [a for a in snapshot["attempts"] if a["status"] == "SUCCEEDED"]
            if attempts:
                timings = (attempts[-1].get("provenance") or {}).get("timing_ms", {})
        table.append(
            dict(
                sample_id=row["id"],
                condition=row["condition"],
                receipt_id=row["receipt_id"],
                input_sha256=row["input_sha256"],
                processing_success=row["processing_success"],
                workflow_status=row["status"],
                stage=error.get("stage"),
                code=error.get("code"),
                upload_ms=row["upload_ms"],
                processing_wall_ms=row["processing_wall_ms"],
                total_ms=row["total_ms"],
                document_reading_ms=timings.get("document_reading"),
                kie_ms=timings.get("kie"),
            )
        )
    (output / "machine_predictions.jsonl").write_text(
        "".join(
            json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in indexes
        ),
        encoding="utf-8",
    )
    fields = list(table[0]) if table else []
    write_csv(output / "samples.csv", table, fields)
    write_csv(
        output / "failures.csv",
        [r for r in table if r["workflow_status"] == "failed"],
        fields,
    )
    expected = len(manifest["samples"])
    success = sum(row["processing_success"] for row in rows)
    metrics = dict(
        scope="system_workflow_only",
        expected_samples=expected,
        attempted_samples=len(rows),
        complete=len(rows) == expected,
        processing_succeeded=success,
        processing_failed=len(rows) - success,
        not_attempted=expected - len(rows),
        processing_success_rate=success / expected,
        workflow_failed=sum(r["status"] == "failed" for r in rows),
        workflow_verified=sum(r["status"] == "verified" for r in rows),
        failures_by_stage=dict(Counter(r["stage"] for r in table if r["stage"])),
        accuracy=None,
        accuracy_status="NOT_SCORED",
        accuracy_reason="No approved source-gold scoring protocol is executed by this capture runner; pending QA and reviewed values cannot establish AI accuracy.",
    )
    write_json(output / "metrics.json", metrics)
    write_csv(
        output / "metrics.csv",
        [
            dict(metric=k, value=v)
            for k, v in metrics.items()
            if not isinstance(v, dict)
        ],
        ["metric", "value"],
    )
    metadata = json.loads((output / "run.json").read_text(encoding="utf-8"))
    metadata["dataset"] = {
        k: manifest.get(k)
        for k in (
            "dataset",
            "version",
            "split",
            "synthetic",
            "qa_status",
            "purpose",
            "provenance",
        )
    }
    metadata["artifact_schema_version"] = "backend-capture-1.1"
    metadata["machine_predictions"] = "machine_predictions.jsonl"
    metadata["sample_count"] = expected
    write_json(output / "run_metadata.json", metadata)
