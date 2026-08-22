from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from ai.kie.config import CONFIG_PATH, load_baseline_config
from ai.kie.contract import validate_ocr_result
from ai.kie.evaluation.metrics import (
    EvaluationPair,
    compute_field_metrics,
)
from ai.kie.pipeline import (
    EXTRACTOR_NAME,
    EXTRACTOR_VERSION,
    FIELD_NAMES,
    run_kie,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "kie_evaluation"
    / "manifest.json"
)
DEFAULT_SPLIT_PATH = (
    PROJECT_ROOT
    / "ai"
    / "kie"
    / "resources"
    / "kie-evaluation-split-v0.1.csv"
)
DEFAULT_REPORT_PATH = (
    PROJECT_ROOT
    / "results"
    / "kie_evaluation_report.json"
)
ANNOTATION_SCHEMA_PATH = (
    PROJECT_ROOT
    / "schemas"
    / "annotation-record.schema.json"
)


EVALUATOR_VERSION = "kie-field-evaluator-v0.1"
WAITING_STATUS = (
    "WAITING_FOR_VERIFIED_FIELD_ANNOTATIONS"
)
COMPLETED_STATUS = "COMPLETED"
VERIFIED_QA_STATE = "VERIFIED"
EVALUATION_NAMESPACE = UUID(
    "d5e246fd-7417-497e-8778-190cde3df1a1"
)


METRIC_NAMES = (
    "exact_match_accuracy",
    "status_accuracy",
    "normalization_accuracy",
    "precision",
    "recall",
    "f1",
    "coverage",
    "review_rate",
)


METRIC_DEFINITIONS = {
    "exact_match_accuracy": (
        "gold and prediction have the same status and normalized value"
    ),
    "status_accuracy": (
        "predicted value_status equals gold annotation_status"
    ),
    "normalization_accuracy": (
        "exact normalized-value matches divided by gold PRESENT fields"
    ),
    "precision": (
        "exact PRESENT matches divided by predicted PRESENT fields; "
        "a wrong PRESENT value is a false positive"
    ),
    "recall": (
        "exact PRESENT matches divided by gold PRESENT fields; "
        "a wrong PRESENT value is a false negative"
    ),
    "f1": "harmonic mean of extraction precision and recall",
    "coverage": "predicted PRESENT fields divided by all field decisions",
    "review_rate": (
        "machine_needs_review fields divided by all field decisions"
    ),
}


ERROR_TAXONOMY_DEFINITIONS = {
    "MISSED_PRESENT": (
        "gold is PRESENT but the machine status is not PRESENT"
    ),
    "SPURIOUS_PRESENT": (
        "machine status is PRESENT but gold is not PRESENT"
    ),
    "STATUS_MISMATCH": (
        "gold and machine non-equivalent statuses differ"
    ),
    "NORMALIZATION_MISMATCH": (
        "both statuses are PRESENT but normalized values differ"
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)

    if not isinstance(document, dict):
        raise ValueError(
            f"JSON document must be an object: {path}"
        )

    return document


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _resolve_input_path(value: str) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _load_split(
    split_path: Path,
) -> tuple[list[dict[str, str]], str]:
    with split_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError(
            f"KIE evaluation split is empty: {split_path}"
        )

    required_columns = {
        "test_id",
        "selection_stratum",
        "kie_split",
        "split_version",
        "split_seed",
    }

    if set(rows[0]) != required_columns:
        raise ValueError(
            "KIE evaluation split columns must be exactly: "
            + ", ".join(sorted(required_columns))
        )

    test_ids = [row["test_id"] for row in rows]

    if len(test_ids) != len(set(test_ids)):
        raise ValueError(
            "KIE evaluation split contains duplicate test_id values"
        )

    invalid_splits = sorted(
        {
            row["kie_split"]
            for row in rows
            if row["kie_split"]
            not in {"development", "held_out"}
        }
    )

    if invalid_splits:
        raise ValueError(
            "Unsupported kie_split values: "
            + ", ".join(invalid_splits)
        )

    versions = {
        row["split_version"]
        for row in rows
    }

    if len(versions) != 1:
        raise ValueError(
            "KIE evaluation split must use one split_version"
        )

    return rows, next(iter(versions))


def _annotation_validator() -> Draft202012Validator:
    schema = _load_json(
        ANNOTATION_SCHEMA_PATH
    )
    Draft202012Validator.check_schema(schema)

    return Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )


def _validate_annotation(
    annotation: dict[str, Any],
    *,
    annotation_path: Path,
) -> None:
    validator = _annotation_validator()
    errors = sorted(
        validator.iter_errors(annotation),
        key=lambda error: [
            str(part)
            for part in error.absolute_path
        ],
    )

    if errors:
        messages = [
            (
                f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
                f"{error.message}"
            )
            for error in errors
        ]
        raise ValueError(
            f"Invalid annotation record {annotation_path}:\n"
            + "\n".join(messages)
        )

    if annotation["example_only"]:
        raise ValueError(
            "Example-only annotation cannot be used for evaluation: "
            f"{annotation_path}"
        )


def _validate_annotation_linkage(
    annotation: dict[str, Any],
    real_ocr: dict[str, Any],
    oracle_ocr: dict[str, Any],
    *,
    test_id: str,
) -> None:
    receipt_ids = {
        annotation["receipt_id"],
        real_ocr["receipt_id"],
        oracle_ocr["receipt_id"],
    }

    if len(receipt_ids) != 1:
        raise ValueError(
            f"{test_id}: annotation, Real OCR and Oracle OCR "
            "must reference the same receipt_id"
        )

    if (
        annotation["source_ocr_run_id"]
        != real_ocr["ocr_run_id"]
    ):
        raise ValueError(
            f"{test_id}: annotation source_ocr_run_id must "
            "reference the Real OCR run"
        )

    if (
        real_ocr["ocr_run_id"]
        == oracle_ocr["ocr_run_id"]
    ):
        raise ValueError(
            f"{test_id}: Real OCR and Oracle OCR must use "
            "different ocr_run_id values"
        )

    real_block_ids = {
        block["block_id"]
        for block in real_ocr["blocks"]
    }

    for field_name in FIELD_NAMES:
        annotation_field = annotation[
            "fields"
        ][field_name]
        unknown_ids = sorted(
            set(annotation_field["source_block_ids"])
            - real_block_ids
        )

        if unknown_ids:
            raise ValueError(
                f"{test_id}/{field_name}: annotation references "
                "unknown Real OCR block IDs: "
                + ", ".join(unknown_ids)
            )


def _base_provenance(
    *,
    manifest_path: Path,
    split_path: Path,
    split_version: str,
) -> dict[str, Any]:
    config = load_baseline_config()

    return {
        "evaluator_version": EVALUATOR_VERSION,
        "extractor": {
            "name": EXTRACTOR_NAME,
            "version": EXTRACTOR_VERSION,
        },
        "ranking_config_version": config["version"],
        "ranking_config_sha256": _sha256(CONFIG_PATH),
        "manifest_path": _display_path(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "split_path": _display_path(split_path),
        "split_version": split_version,
        "split_sha256": _sha256(split_path),
        "annotation_schema_sha256": _sha256(
            ANNOTATION_SCHEMA_PATH
        ),
    }


def _waiting_report(
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    split_path: Path,
    split_rows: list[dict[str, str]],
    split_version: str,
    reasons: list[str],
) -> dict[str, Any]:
    records = manifest.get("records", [])
    record_ids = {
        record.get("test_id")
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("test_id"), str)
    }
    split_counts = Counter(
        row["kie_split"]
        for row in split_rows
    )

    return {
        "status": WAITING_STATUS,
        "dataset_version": manifest.get(
            "dataset_version"
        ),
        "annotation_qa_state": manifest.get(
            "annotation_qa_state"
        ),
        "reasons": list(dict.fromkeys(reasons)),
        "sample_counts": {
            "required": len(split_rows),
            "manifest_records": len(records),
            "ready_test_ids": len(
                record_ids
                & {
                    row["test_id"]
                    for row in split_rows
                }
            ),
            "development_required": split_counts[
                "development"
            ],
            "held_out_required": split_counts[
                "held_out"
            ],
            "evaluated": 0,
        },
        "metrics": None,
        "metric_definitions": METRIC_DEFINITIONS,
        "error_taxonomy_definitions": (
            ERROR_TAXONOMY_DEFINITIONS
        ),
        "modes": None,
        "propagation_gap": None,
        "provenance": _base_provenance(
            manifest_path=manifest_path,
            split_path=split_path,
            split_version=split_version,
        ),
    }


def _metric_gap(
    oracle: dict[str, Any],
    real: dict[str, Any],
) -> dict[str, float]:
    return {
        metric_name: round(
            float(oracle[metric_name])
            - float(real[metric_name]),
            6,
        )
        for metric_name in METRIC_NAMES
    }


def _propagation_gap(
    *,
    real_metrics: dict[str, Any],
    oracle_metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "definition": "oracle_metric_minus_real_metric",
        "overall": _metric_gap(
            oracle_metrics["overall"],
            real_metrics["overall"],
        ),
        "fields": {
            field_name: _metric_gap(
                oracle_metrics["fields"][field_name],
                real_metrics["fields"][field_name],
            )
            for field_name in FIELD_NAMES
        },
    }


def _evaluation_run_id(
    *,
    dataset_version: str,
    test_id: str,
    mode: str,
    ocr_run_id: str,
    config_sha256: str,
) -> UUID:
    return uuid5(
        EVALUATION_NAMESPACE,
        "|".join(
            (
                dataset_version,
                test_id,
                mode,
                ocr_run_id,
                EXTRACTOR_VERSION,
                config_sha256,
            )
        ),
    )


def evaluate_manifest(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    *,
    split_path: str | Path = DEFAULT_SPLIT_PATH,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    split_path = Path(split_path)
    manifest = _load_json(manifest_path)
    split_rows, split_version = _load_split(split_path)

    records = manifest.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "KIE evaluation manifest records must be a list"
        )

    if manifest.get("example_only") is True:
        raise ValueError(
            "Example-only manifest cannot be used for evaluation"
        )

    dataset_version = manifest.get("dataset_version")

    if not isinstance(dataset_version, str) or not dataset_version:
        raise ValueError(
            "KIE evaluation manifest requires dataset_version"
        )

    record_ids = [
        record.get("test_id")
        for record in records
        if isinstance(record, dict)
    ]

    if len(record_ids) != len(records):
        raise ValueError(
            "Every KIE evaluation record must be an object"
        )

    if any(
        not isinstance(test_id, str)
        or not test_id
        for test_id in record_ids
    ):
        raise ValueError(
            "Every KIE evaluation record requires test_id"
        )

    if len(record_ids) != len(set(record_ids)):
        raise ValueError(
            "KIE evaluation manifest contains duplicate test_id values"
        )

    split_ids = {
        row["test_id"]
        for row in split_rows
    }
    extra_ids = sorted(
        set(record_ids) - split_ids
    )

    if extra_ids:
        raise ValueError(
            "Manifest test IDs are outside the frozen split: "
            + ", ".join(extra_ids)
        )

    reasons: list[str] = []

    if (
        manifest.get("annotation_qa_state")
        != VERIFIED_QA_STATE
    ):
        reasons.append(
            "annotation_qa_state is not VERIFIED"
        )

    if not manifest.get("annotation_provenance"):
        reasons.append(
            "annotation_provenance is missing"
        )

    if not records:
        reasons.append(
            "no verified five-field annotation records are available"
        )

    missing_ids = sorted(
        split_ids - set(record_ids)
    )

    if missing_ids:
        reasons.append(
            "manifest is missing frozen split test IDs: "
            + ", ".join(missing_ids)
        )

    resolved_records: list[
        tuple[
            dict[str, Any],
            Path | None,
            Path | None,
            Path | None,
        ]
    ] = []

    for record in records:
        test_id = record["test_id"]

        if (
            record.get("oracle_qa_state")
            != VERIFIED_QA_STATE
        ):
            reasons.append(
                f"{test_id}: oracle_qa_state is not VERIFIED"
            )

        if not record.get("oracle_provenance"):
            reasons.append(
                f"{test_id}: oracle_provenance is missing"
            )

        paths: list[Path | None] = []

        for key in (
            "annotation_path",
            "real_ocr_path",
            "oracle_ocr_path",
        ):
            value = record.get(key)

            if not isinstance(value, str) or not value:
                reasons.append(
                    f"{test_id}: {key} is missing"
                )
                paths.append(None)
                continue

            path = _resolve_input_path(value)
            paths.append(path)

            if not path.is_file():
                reasons.append(
                    f"{test_id}: {key} does not exist: {path}"
                )

        annotation_path, real_path, oracle_path = paths

        if (
            real_path is not None
            and oracle_path is not None
            and real_path.resolve() == oracle_path.resolve()
        ):
            raise ValueError(
                f"{test_id}: Real OCR and Oracle OCR must be "
                "different artifacts"
            )

        resolved_records.append(
            (
                record,
                annotation_path,
                real_path,
                oracle_path,
            )
        )

    if reasons:
        return _waiting_report(
            manifest=manifest,
            manifest_path=manifest_path,
            split_path=split_path,
            split_rows=split_rows,
            split_version=split_version,
            reasons=reasons,
        )

    split_by_test_id = {
        row["test_id"]: row["kie_split"]
        for row in split_rows
    }
    provenance = _base_provenance(
        manifest_path=manifest_path,
        split_path=split_path,
        split_version=split_version,
    )
    config_sha256 = provenance[
        "ranking_config_sha256"
    ]

    pairs_by_mode: dict[str, list[EvaluationPair]] = {
        "real": [],
        "oracle": [],
    }
    input_hashes: dict[str, dict[str, str]] = {}
    kie_runs: dict[str, dict[str, dict[str, str]]] = {
        "real": {},
        "oracle": {},
    }

    for (
        record,
        annotation_path,
        real_path,
        oracle_path,
    ) in resolved_records:
        if (
            annotation_path is None
            or real_path is None
            or oracle_path is None
        ):
            raise AssertionError(
                "ready evaluation record has unresolved paths"
            )

        test_id = record["test_id"]
        annotation = _load_json(annotation_path)
        real_ocr = _load_json(real_path)
        oracle_ocr = _load_json(oracle_path)

        _validate_annotation(
            annotation,
            annotation_path=annotation_path,
        )
        validate_ocr_result(real_ocr)
        validate_ocr_result(oracle_ocr)
        _validate_annotation_linkage(
            annotation,
            real_ocr,
            oracle_ocr,
            test_id=test_id,
        )

        input_hashes[test_id] = {
            "annotation_sha256": _sha256(
                annotation_path
            ),
            "real_ocr_sha256": _sha256(real_path),
            "oracle_ocr_sha256": _sha256(
                oracle_path
            ),
        }

        for mode, ocr_result in (
            ("real", real_ocr),
            ("oracle", oracle_ocr),
        ):
            kie_run_id = _evaluation_run_id(
                dataset_version=dataset_version,
                test_id=test_id,
                mode=mode,
                ocr_run_id=ocr_result["ocr_run_id"],
                config_sha256=config_sha256,
            )
            kie_result = run_kie(
                ocr_result,
                kie_run_id=kie_run_id,
            )
            pairs_by_mode[mode].append(
                (
                    test_id,
                    annotation,
                    kie_result,
                )
            )
            kie_runs[mode][test_id] = {
                "kie_run_id": str(kie_run_id),
                "source_ocr_run_id": ocr_result[
                    "ocr_run_id"
                ],
            }

    modes: dict[str, Any] = {}

    for mode, pairs in pairs_by_mode.items():
        all_metrics = compute_field_metrics(pairs)
        modes[mode] = {
            "all": all_metrics,
            "by_split": {
                split_name: compute_field_metrics(
                    [
                        pair
                        for pair in pairs
                        if split_by_test_id[pair[0]]
                        == split_name
                    ]
                )
                for split_name in (
                    "development",
                    "held_out",
                )
            },
        }

    split_counts = Counter(
        split_by_test_id.values()
    )
    provenance["input_artifact_sha256"] = input_hashes

    return {
        "status": COMPLETED_STATUS,
        "dataset_version": dataset_version,
        "annotation_qa_state": manifest[
            "annotation_qa_state"
        ],
        "sample_counts": {
            "required": len(split_rows),
            "manifest_records": len(records),
            "evaluated": len(records),
            "development": split_counts[
                "development"
            ],
            "held_out": split_counts["held_out"],
        },
        "metric_definitions": METRIC_DEFINITIONS,
        "error_taxonomy_definitions": (
            ERROR_TAXONOMY_DEFINITIONS
        ),
        "modes": modes,
        "propagation_gap": _propagation_gap(
            real_metrics=modes["real"]["all"],
            oracle_metrics=modes["oracle"]["all"],
        ),
        "kie_runs": kie_runs,
        "provenance": provenance,
    }


def write_evaluation_report(
    report: dict[str, Any],
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> Path:
    report_path = Path(report_path)
    serialized = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_path.write_text(
        serialized,
        encoding="utf-8",
    )

    return report_path
