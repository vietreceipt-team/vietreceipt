"""Immutable local artifact persistence for evaluation and reproducibility only."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .contract import validate_ocr_result


class ImmutableOCRArtifactStore:
    """Write each run once; Backend remains responsible for production persistence."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path_for(self, document: dict[str, Any]) -> Path:
        return self.root / document["receipt_id"] / f"{document['ocr_run_id']}.json"

    def write(self, document: dict[str, Any]) -> Path:
        validate_ocr_result(document)
        target = self.path_for(document)
        target.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            descriptor = os.open(target, flags, 0o600)
        except FileExistsError as exc:
            raise FileExistsError(
                f"Refusing to overwrite immutable OCR run: {target}"
            ) from exc
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return target
