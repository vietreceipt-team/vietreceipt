"""Real compose smoke: upload a receipt and wait for PostgreSQL NEEDS_REVIEW."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg
from psycopg.rows import dict_row


EXPECTED_FIELD_NAMES = frozenset(
    {
        "merchant_name",
        "receipt_date",
        "total_amount",
        "invoice_id",
        "merchant_address",
    }
)


@dataclass(frozen=True)
class FieldEvidence:
    field_name: str
    receipt_id: str
    ocr_run_id: str
    kie_run_id: str


@dataclass(frozen=True)
class ProcessingEvidence:
    receipt_id: str
    receipt_status: str | None
    receipt_error: dict[str, Any] | None
    latest_ocr_run_id: str | None
    latest_kie_run_id: str | None
    attempt_id: str | None
    attempt_status: str | None
    attempt_stage: str | None
    attempt_ocr_run_id: str | None
    attempt_kie_run_id: str | None
    attempt_error: dict[str, Any] | None
    ocr_record_id: str | None
    ocr_attempt_id: str | None
    ocr_receipt_id: str | None
    kie_record_id: str | None
    kie_attempt_id: str | None
    kie_receipt_id: str | None
    kie_source_ocr_run_id: str | None
    fields: tuple[FieldEvidence, ...]


def _as_text(value: Any | None) -> str | None:
    return str(value) if value is not None else None


def build_evidence(
    receipt_id: str,
    receipt_row: Mapping[str, Any] | None,
    field_rows: Sequence[Mapping[str, Any]],
) -> ProcessingEvidence:
    row = receipt_row or {}
    fields = tuple(
        FieldEvidence(
            field_name=str(field["field_name"]),
            receipt_id=str(field["receipt_id"]),
            ocr_run_id=str(field["ocr_run_id"]),
            kie_run_id=str(field["kie_run_id"]),
        )
        for field in field_rows
    )
    return ProcessingEvidence(
        receipt_id=receipt_id,
        receipt_status=row.get("receipt_status"),
        receipt_error=row.get("receipt_error"),
        latest_ocr_run_id=_as_text(row.get("latest_ocr_run_id")),
        latest_kie_run_id=_as_text(row.get("latest_kie_run_id")),
        attempt_id=_as_text(row.get("attempt_id")),
        attempt_status=row.get("attempt_status"),
        attempt_stage=row.get("attempt_stage"),
        attempt_ocr_run_id=_as_text(row.get("attempt_ocr_run_id")),
        attempt_kie_run_id=_as_text(row.get("attempt_kie_run_id")),
        attempt_error=row.get("attempt_error"),
        ocr_record_id=_as_text(row.get("ocr_record_id")),
        ocr_attempt_id=_as_text(row.get("ocr_attempt_id")),
        ocr_receipt_id=_as_text(row.get("ocr_receipt_id")),
        kie_record_id=_as_text(row.get("kie_record_id")),
        kie_attempt_id=_as_text(row.get("kie_attempt_id")),
        kie_receipt_id=_as_text(row.get("kie_receipt_id")),
        kie_source_ocr_run_id=_as_text(
            row.get("kie_source_ocr_run_id")
        ),
        fields=fields,
    )


def fetch_evidence(
    connection: psycopg.Connection,
    receipt_id: str,
) -> ProcessingEvidence:
    receipt_row = connection.execute(
        """
        SELECT
            r.status AS receipt_status,
            r.last_error AS receipt_error,
            r.latest_ocr_run_id,
            r.latest_kie_run_id,
            pa.attempt_id,
            pa.status AS attempt_status,
            pa.stage AS attempt_stage,
            pa.ocr_run_id AS attempt_ocr_run_id,
            pa.kie_run_id AS attempt_kie_run_id,
            pa.error AS attempt_error,
            o.ocr_run_id AS ocr_record_id,
            o.attempt_id AS ocr_attempt_id,
            o.receipt_id AS ocr_receipt_id,
            k.kie_run_id AS kie_record_id,
            k.attempt_id AS kie_attempt_id,
            k.receipt_id AS kie_receipt_id,
            k.source_ocr_run_id AS kie_source_ocr_run_id
        FROM receipts AS r
        LEFT JOIN LATERAL (
            SELECT attempt.*
            FROM processing_attempts AS attempt
            WHERE attempt.receipt_id = r.receipt_id
            ORDER BY attempt.started_at DESC, attempt.attempt_id DESC
            LIMIT 1
        ) AS pa ON TRUE
        LEFT JOIN ocr_runs AS o
            ON o.ocr_run_id = pa.ocr_run_id
        LEFT JOIN kie_runs AS k
            ON k.kie_run_id = pa.kie_run_id
        WHERE r.receipt_id = %s
        """,
        (receipt_id,),
    ).fetchone()
    field_rows = connection.execute(
        """
        SELECT field_name, receipt_id, ocr_run_id, kie_run_id
        FROM extracted_fields
        WHERE receipt_id = %s
        ORDER BY field_name
        """,
        (receipt_id,),
    ).fetchall()
    return build_evidence(receipt_id, receipt_row, field_rows)


def validation_errors(evidence: ProcessingEvidence) -> tuple[str, ...]:
    errors: list[str] = []

    if evidence.receipt_status != "NEEDS_REVIEW":
        errors.append(
            "receipt_status="
            f"{evidence.receipt_status or '-'} expected=NEEDS_REVIEW"
        )
    if evidence.attempt_id is None:
        errors.append("processing_attempt missing")
    if evidence.attempt_status != "SUCCEEDED":
        errors.append(
            "attempt_status="
            f"{evidence.attempt_status or '-'} expected=SUCCEEDED"
        )
    if evidence.attempt_stage != "PERSISTING":
        errors.append(
            "attempt_stage="
            f"{evidence.attempt_stage or '-'} expected=PERSISTING"
        )

    if (
        evidence.latest_ocr_run_id is None
        or evidence.attempt_ocr_run_id != evidence.latest_ocr_run_id
    ):
        errors.append("attempt OCR run does not match receipt latest OCR run")
    if (
        evidence.latest_kie_run_id is None
        or evidence.attempt_kie_run_id != evidence.latest_kie_run_id
    ):
        errors.append("attempt KIE run does not match receipt latest KIE run")

    if (
        evidence.ocr_record_id != evidence.latest_ocr_run_id
        or evidence.ocr_attempt_id != evidence.attempt_id
        or evidence.ocr_receipt_id != evidence.receipt_id
    ):
        errors.append("OCR run linkage is incomplete")
    if (
        evidence.kie_record_id != evidence.latest_kie_run_id
        or evidence.kie_attempt_id != evidence.attempt_id
        or evidence.kie_receipt_id != evidence.receipt_id
        or evidence.kie_source_ocr_run_id != evidence.latest_ocr_run_id
    ):
        errors.append("KIE run linkage is incomplete")

    if len(evidence.fields) != 5:
        errors.append(
            f"canonical_field_count={len(evidence.fields)} expected=5"
        )

    actual_field_names = {field.field_name for field in evidence.fields}
    if actual_field_names != EXPECTED_FIELD_NAMES:
        missing = ",".join(sorted(EXPECTED_FIELD_NAMES - actual_field_names))
        unexpected = ",".join(
            sorted(actual_field_names - EXPECTED_FIELD_NAMES)
        )
        errors.append(
            "canonical_fields "
            f"missing={missing or '-'} unexpected={unexpected or '-'}"
        )

    if any(
        field.receipt_id != evidence.receipt_id
        or field.ocr_run_id != evidence.latest_ocr_run_id
        or field.kie_run_id != evidence.latest_kie_run_id
        for field in evidence.fields
    ):
        errors.append(
            "extracted_fields linkage does not match receipt/OCR/KIE runs"
        )

    return tuple(errors)


def format_success_lines(evidence: ProcessingEvidence) -> tuple[str, ...]:
    return (
        "PASS processing E2E",
        f"receipt_id={evidence.receipt_id}",
        f"attempt_id={evidence.attempt_id}",
        f"ocr_run_id={evidence.attempt_ocr_run_id}",
        f"kie_run_id={evidence.attempt_kie_run_id}",
        f"status={evidence.receipt_status}",
        f"attempt_status={evidence.attempt_status}",
        f"attempt_stage={evidence.attempt_stage}",
        f"latest_ocr_run_id={evidence.latest_ocr_run_id}",
        f"latest_kie_run_id={evidence.latest_kie_run_id}",
        f"canonical_field_count={len(evidence.fields)}",
    )


def format_failure_lines(
    evidence: ProcessingEvidence,
    *,
    reason: str,
) -> tuple[str, ...]:
    lines = [
        "FAIL processing E2E",
        f"reason={reason}",
        f"receipt_id={evidence.receipt_id}",
        f"status={evidence.receipt_status or '-'}",
        f"attempt_id={evidence.attempt_id or '-'}",
        f"attempt_status={evidence.attempt_status or '-'}",
        f"attempt_stage={evidence.attempt_stage or '-'}",
        f"ocr_run_id={evidence.attempt_ocr_run_id or '-'}",
        f"kie_run_id={evidence.attempt_kie_run_id or '-'}",
        f"canonical_field_count={len(evidence.fields)}",
    ]
    error = evidence.attempt_error or evidence.receipt_error
    if error:
        lines.extend(
            (
                f"error_stage={error.get('stage', '-')}",
                f"error_code={error.get('code', '-')}",
                "error_retryable="
                f"{error.get('retryable', '-')}",
            )
        )
    return tuple(lines)


def main() -> None:
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

    deadline = time.monotonic() + int(
        os.getenv("SMOKE_TIMEOUT_SECONDS", "300")
    )
    evidence = build_evidence(receipt_id, None, ())
    while time.monotonic() < deadline:
        with psycopg.connect(
            database_url,
            row_factory=dict_row,
        ) as connection:
            evidence = fetch_evidence(connection, receipt_id)
        if evidence.receipt_status == "NEEDS_REVIEW":
            errors = validation_errors(evidence)
            if errors:
                print(
                    "\n".join(
                        format_failure_lines(
                            evidence,
                            reason="; ".join(errors),
                        )
                    ),
                    file=sys.stderr,
                )
                raise SystemExit(1)
            print("\n".join(format_success_lines(evidence)))
            raise SystemExit(0)
        if evidence.receipt_status == "FAILED":
            print(
                "\n".join(
                    format_failure_lines(
                        evidence,
                        reason="receipt reached FAILED",
                    )
                ),
                file=sys.stderr,
            )
            raise SystemExit(1)
        time.sleep(2)

    print(
        "\n".join(
            format_failure_lines(
                evidence,
                reason="timed out waiting for NEEDS_REVIEW",
            )
        ),
        file=sys.stderr,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    main()
