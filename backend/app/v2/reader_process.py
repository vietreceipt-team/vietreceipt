"""Private one-document subprocess protocol. No database access or review data."""

import json
import sys
from pathlib import Path

from ai.document_reader.pipeline import ReaderError, read_document


def main():
    folder = Path(sys.argv[1])
    request = json.loads((folder / "request.json").read_text())
    try:
        result = {
            "evidence": read_document((folder / "source").read_bytes(), **request)
        }
    except ReaderError as exc:
        result = {
            "error": dict(code=exc.code, message=str(exc), retryable=exc.retryable)
        }
    (folder / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, allow_nan=False)
    )


if __name__ == "__main__":
    main()
