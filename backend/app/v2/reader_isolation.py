"""Keep native PDFium/Paddle crashes outside the Celery processing transaction."""

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from .errors import V2Error


def read_isolated(data, *, content_type, receipt_id, ocr_run_id):
    try:
        timeout = float(os.getenv("V2_READER_TIMEOUT_SECONDS", "780"))
        if not math.isfinite(timeout) or not 0 < timeout <= 800:
            raise ValueError()
    except ValueError as exc:
        raise V2Error(
            "INVALID_READER_CONFIG",
            "Reader timeout must be in (0, 800] seconds.",
            503,
            False,
        ) from exc
    with TemporaryDirectory(prefix="vietreceipt-reader-") as folder:
        root = Path(folder)
        (root / "source").write_bytes(data)
        (root / "request.json").write_text(
            json.dumps(
                dict(
                    content_type=content_type,
                    receipt_id=str(receipt_id),
                    ocr_run_id=str(ocr_run_id),
                )
            )
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "backend.app.v2.reader_process", str(root)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise V2Error(
                "DOCUMENT_READER_TIMEOUT",
                "Document reader exceeded its time limit.",
                503,
                True,
            ) from exc
        if completed.returncode != 0:
            raise V2Error(
                "DOCUMENT_READER_CRASHED",
                f"Document reader process stopped unexpectedly (exit status {completed.returncode}); inspect the OCR runtime before retrying.",
                503,
                True,
            )
        try:
            result = json.loads((root / "result.json").read_text())
            if "error" in result:
                error = result["error"]
                raise V2Error(
                    error["code"],
                    error["message"],
                    503 if error["retryable"] else 422,
                    error["retryable"],
                )
            return result["evidence"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise V2Error(
                "DOCUMENT_READER_PROTOCOL_FAILED",
                "Document reader returned an invalid response.",
                503,
                True,
            ) from exc
