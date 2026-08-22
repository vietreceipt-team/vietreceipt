from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from ai.kie.contract import validate_kie_result
from ai.kie.pipeline import run_kie


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KIE_OUTPUT_ROOT = (
    PROJECT_ROOT
    / "results"
    / "kie_outputs"
)


def kie_artifact_path(
    kie_result: dict[str, Any],
    *,
    output_root: str | Path = DEFAULT_KIE_OUTPUT_ROOT,
) -> Path:
    """
    Resolve the immutable artifact path for one canonical KIE run.

    The KIE contract validation performed by the writer guarantees that
    receipt_id and kie_run_id are canonical UUID strings before this path
    is used for persistence.
    """

    return (
        Path(output_root)
        / kie_result["receipt_id"]
        / f'{kie_result["kie_run_id"]}.json'
    )


def write_kie_artifact(
    kie_result: dict[str, Any],
    *,
    output_root: str | Path = DEFAULT_KIE_OUTPUT_ROOT,
) -> Path:
    """
    Validate and persist one KIE result without ever overwriting it.

    Validation and JSON serialization happen before the destination file
    is created. Opening with mode ``x`` is the filesystem-level guard: an
    existing receipt_id/kie_run_id artifact raises FileExistsError and its
    original bytes remain unchanged.
    """

    validate_kie_result(kie_result)

    serialized = json.dumps(
        kie_result,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    artifact_path = kie_artifact_path(
        kie_result,
        output_root=output_root,
    )
    artifact_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with artifact_path.open(
        "x",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        handle.write(serialized)

    return artifact_path


def run_and_write_kie(
    ocr_result: dict[str, Any],
    *,
    kie_run_id: UUID,
    output_root: str | Path = DEFAULT_KIE_OUTPUT_ROOT,
) -> tuple[dict[str, Any], Path]:
    """
    Run the deterministic baseline and persist its immutable artifact.

    Reprocessing is explicit: the caller must supply a new kie_run_id.
    Reusing an existing ID is rejected by write_kie_artifact.
    """

    result = run_kie(
        ocr_result,
        kie_run_id=kie_run_id,
    )
    artifact_path = write_kie_artifact(
        result,
        output_root=output_root,
    )

    return result, artifact_path
