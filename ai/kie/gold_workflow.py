"""Human-gated Week-3 semantic gold and Oracle OCR workflow.

This module prepares traceable work packets and validates human decisions.  It
never promotes a draft to VERIFIED and never derives semantic labels from OCR
or KIE predictions.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from ai.kie.pipeline import FIELD_NAMES
from ai.ocr.contract import validate_ocr_result


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPLIT_PATH = (
    PROJECT_ROOT
    / "ai"
    / "kie"
    / "resources"
    / "kie-evaluation-split-v0.1.csv"
)
MANIFEST_PATH = PROJECT_ROOT / "data" / "kie_evaluation" / "manifest.json"
REAL_OCR_ROOT = PROJECT_ROOT / "results" / "ocr_outputs"
ANNOTATION_ROOT = PROJECT_ROOT / "data" / "kie_annotations"
ORACLE_ROOT = PROJECT_ROOT / "data" / "kie_oracle_ocr"
ANNOTATION_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "annotation-record.schema.json"
)
ADJUDICATION_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "adjudication-record.schema.json"
)
ORACLE_QA_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "oracle-qa-record.schema.json"
)

WORKFLOW_NAMESPACE = UUID("0f438235-c94c-4f7a-81cd-b190c524f8da")
DATASET_VERSION = "vietreceipt-week1-frozen-40-v1"


@dataclass(frozen=True)
class SamplePaths:
    test_id: str
    real_ocr: Path
    oracle_ocr: Path
    oracle_qa: Path
    annotation_a: Path
    annotation_b: Path
    final_annotation: Path
    adjudication: Path


def paths_for(test_id: str) -> SamplePaths:
    return SamplePaths(
        test_id=test_id,
        real_ocr=REAL_OCR_ROOT / f"{test_id}.json",
        oracle_ocr=ORACLE_ROOT / "drafts" / f"{test_id}.json",
        oracle_qa=ORACLE_ROOT / "qa" / f"{test_id}.json",
        annotation_a=ANNOTATION_ROOT / "annotator_a" / f"{test_id}.json",
        annotation_b=ANNOTATION_ROOT / "annotator_b" / f"{test_id}.json",
        final_annotation=ANNOTATION_ROOT / "final" / f"{test_id}.json",
        adjudication=ANNOTATION_ROOT / "adjudication" / f"{test_id}.json",
    )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return document


def _write_json_if_missing(path: Path, document: dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return False
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return True


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_rows(split_path: Path = SPLIT_PATH) -> list[dict[str, str]]:
    with split_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row["test_id"] for row in rows]
    expected = [f"R{index:03d}" for index in range(1, 41)]
    if ids != expected:
        raise ValueError("Frozen W3 split must contain exactly ordered R001-R040")
    return rows


def _blank_field(field_name: str) -> dict[str, Any]:
    field: dict[str, Any] = {
        "field_name": field_name,
        "annotation_status": None,
        "transcribed_value": None,
        "normalized_value": None,
        "source_block_ids": [],
        "candidate_values": [],
        "annotator_note": None,
    }
    if field_name == "total_amount":
        field["currency"] = "VND"
    return field


def annotation_draft(
    test_id: str,
    real_ocr: dict[str, Any],
    *,
    slot: str,
) -> dict[str, Any]:
    """Create an intentionally incomplete form without semantic labels."""
    return {
        "record_type": "five-field-ground-truth-annotation",
        "annotation_schema_version": "1.0",
        "guideline_version": "1.1",
        "annotation_id": str(
            uuid5(WORKFLOW_NAMESPACE, f"{test_id}:annotation:{slot}")
        ),
        "batch_id": f"w3-gold-{slot}",
        "dataset_snapshot": DATASET_VERSION,
        "example_only": False,
        "data_provenance": "",
        "receipt_id": real_ocr["receipt_id"],
        "source_ocr_run_id": real_ocr["ocr_run_id"],
        "annotator_id": "",
        "annotated_at": None,
        "fields": {
            field_name: _blank_field(field_name)
            for field_name in FIELD_NAMES
        },
    }


def oracle_draft(test_id: str, real_ocr: dict[str, Any]) -> dict[str, Any]:
    """Bootstrap a PENDING draft while preserving canonical block geometry.

    The copied text and confidence remain unverified Real OCR evidence.  A
    human must correct blocks, document omissions/substitutions and complete a
    separate QA record before this file can be treated as Oracle evidence.
    """
    draft = copy.deepcopy(real_ocr)
    draft["ocr_run_id"] = str(
        uuid5(WORKFLOW_NAMESPACE, f"{test_id}:oracle-ocr-draft")
    )
    draft["engine"] = {
        "name": "human-oracle-draft-from-real-ocr",
        "version": "w3-draft-v0.1",
    }
    draft["duration_ms"] = 0
    validate_ocr_result(draft)
    return draft


def oracle_qa_draft(
    test_id: str,
    real_ocr: dict[str, Any],
    oracle_ocr: dict[str, Any],
) -> dict[str, Any]:
    """Create an intentionally incomplete independent-QA form."""
    return {
        "record_type": "oracle-ocr-independent-qa",
        "schema_version": "1.0",
        "test_id": test_id,
        "receipt_id": real_ocr["receipt_id"],
        "real_ocr_run_id": real_ocr["ocr_run_id"],
        "oracle_ocr_run_id": oracle_ocr["ocr_run_id"],
        "oracle_sha256": "",
        "prepared_by": "",
        "prepared_at": None,
        "reviewer_id": "",
        "reviewed_at": None,
        "independent_review_confirmed": False,
        "qa_state": "PENDING",
        "provenance": "",
        "real_vs_oracle_findings": {
            "omissions": [],
            "substitutions": [],
            "other": [],
        },
    }


def pending_manifest() -> dict[str, Any]:
    records = []
    for row in split_rows():
        sample = paths_for(row["test_id"])
        records.append(
            {
                "test_id": sample.test_id,
                "annotation_a_path": _relative(sample.annotation_a),
                "annotation_b_path": _relative(sample.annotation_b),
                "annotation_path": _relative(sample.final_annotation),
                "adjudication_path": _relative(sample.adjudication),
                "real_ocr_path": _relative(sample.real_ocr),
                "oracle_ocr_path": _relative(sample.oracle_ocr),
                "oracle_qa_path": _relative(sample.oracle_qa),
                "oracle_qa_state": "PENDING_INDEPENDENT_REVIEW",
                "oracle_provenance": None,
            }
        )
    return {
        "dataset_version": DATASET_VERSION,
        "annotation_qa_state": (
            "PENDING_INDEPENDENT_DOUBLE_ANNOTATION_AND_ADJUDICATION"
        ),
        "annotation_provenance": None,
        "example_only": False,
        "records": records,
    }


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def prepare_workspace() -> dict[str, int]:
    """Create W3 forms without overwriting any human-entered file."""
    counts = {
        "real_ocr_valid": 0,
        "annotation_drafts_created": 0,
        "oracle_drafts_created": 0,
        "oracle_qa_drafts_created": 0,
    }
    for row in split_rows():
        test_id = row["test_id"]
        sample = paths_for(test_id)
        real_ocr = load_json(sample.real_ocr)
        validate_ocr_result(real_ocr)
        counts["real_ocr_valid"] += 1

        for slot, target in (
            ("annotator-a", sample.annotation_a),
            ("annotator-b", sample.annotation_b),
        ):
            if _write_json_if_missing(
                target,
                annotation_draft(test_id, real_ocr, slot=slot),
            ):
                counts["annotation_drafts_created"] += 1

        oracle = oracle_draft(test_id, real_ocr)
        if _write_json_if_missing(sample.oracle_ocr, oracle):
            counts["oracle_drafts_created"] += 1
        else:
            oracle = load_json(sample.oracle_ocr)

        if _write_json_if_missing(
            sample.oracle_qa,
            oracle_qa_draft(test_id, real_ocr, oracle),
        ):
            counts["oracle_qa_drafts_created"] += 1
    return counts


def _validator(schema_path: Path) -> Draft202012Validator:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def schema_errors(document: dict[str, Any], schema_path: Path) -> list[str]:
    errors = sorted(
        _validator(schema_path).iter_errors(document),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    return [
        f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in errors
    ]


def annotation_errors(
    annotation: dict[str, Any],
    real_ocr: dict[str, Any],
) -> list[str]:
    errors = schema_errors(annotation, ANNOTATION_SCHEMA_PATH)
    if annotation.get("receipt_id") != real_ocr.get("receipt_id"):
        errors.append("receipt_id does not match Real OCR")
    if annotation.get("source_ocr_run_id") != real_ocr.get("ocr_run_id"):
        errors.append("source_ocr_run_id does not match Real OCR")
    known_blocks = {
        block["block_id"] for block in real_ocr.get("blocks", [])
    }
    for field_name, field in annotation.get("fields", {}).items():
        for block_id in field.get("source_block_ids", []):
            if block_id not in known_blocks:
                errors.append(f"{field_name}: unknown Real OCR block {block_id}")
    return errors


def semantic_label(field: dict[str, Any]) -> dict[str, Any]:
    """Return the protocol fields used to decide A/B agreement."""
    return {
        "annotation_status": field.get("annotation_status"),
        "normalized_value": field.get("normalized_value"),
        "candidate_values": field.get("candidate_values", []),
        "source_block_ids": field.get("source_block_ids", []),
    }


def disagreement_fields(
    annotation_a: dict[str, Any],
    annotation_b: dict[str, Any],
) -> list[str]:
    return [
        field_name
        for field_name in FIELD_NAMES
        if semantic_label(annotation_a["fields"][field_name])
        != semantic_label(annotation_b["fields"][field_name])
    ]


def create_adjudication_forms(test_id: str) -> list[str]:
    """Create final/adjudication drafts only after valid independent A/B."""
    sample = paths_for(test_id)
    real = load_json(sample.real_ocr)
    annotation_a = load_json(sample.annotation_a)
    annotation_b = load_json(sample.annotation_b)
    errors = [
        f"annotation A: {error}"
        for error in annotation_errors(annotation_a, real)
    ]
    errors.extend(
        f"annotation B: {error}"
        for error in annotation_errors(annotation_b, real)
    )
    if errors:
        raise ValueError("A/B annotations are not ready:\n" + "\n".join(errors))
    if annotation_a["annotator_id"] == annotation_b["annotator_id"]:
        raise ValueError("Annotator A and B must be different people")

    disagreements = disagreement_fields(annotation_a, annotation_b)
    final = copy.deepcopy(annotation_a)
    final["annotation_id"] = str(
        uuid5(WORKFLOW_NAMESPACE, f"{test_id}:annotation:final")
    )
    final["batch_id"] = "w3-gold-final"
    final["annotator_id"] = ""
    final["annotated_at"] = None
    final["data_provenance"] = ""
    for field_name in disagreements:
        final["fields"][field_name] = _blank_field(field_name)

    adjudication = {
        "record_type": "five-field-annotation-adjudication",
        "schema_version": "1.0",
        "test_id": test_id,
        "receipt_id": real["receipt_id"],
        "source_ocr_run_id": real["ocr_run_id"],
        "annotation_a_id": annotation_a["annotation_id"],
        "annotation_b_id": annotation_b["annotation_id"],
        "adjudicator_id": "",
        "adjudicated_at": None,
        "independent_review_confirmed": False,
        "disagreements": {
            field_name: {
                "annotation_a": semantic_label(
                    annotation_a["fields"][field_name]
                ),
                "annotation_b": semantic_label(
                    annotation_b["fields"][field_name]
                ),
                "final": semantic_label(final["fields"][field_name]),
                "decision_reason": "",
                "rule_reference": "",
            }
            for field_name in disagreements
        },
    }
    _write_json_if_missing(sample.final_annotation, final)
    if disagreements:
        _write_json_if_missing(sample.adjudication, adjudication)
    return disagreements


def _manifest_by_id() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = load_json(MANIFEST_PATH)
    records = manifest.get("records", [])
    return manifest, {record["test_id"]: record for record in records}


def _oracle_qa_errors(
    test_id: str,
    sample: SamplePaths,
    real: dict[str, Any],
    oracle: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    qa = load_json(sample.oracle_qa)
    errors.extend(
        f"Oracle QA: {error}"
        for error in schema_errors(qa, ORACLE_QA_SCHEMA_PATH)
    )
    if qa.get("prepared_by") == qa.get("reviewer_id"):
        errors.append("Oracle preparer and reviewer must be different")
    expected_qa = {
        "test_id": test_id,
        "receipt_id": real.get("receipt_id"),
        "real_ocr_run_id": real.get("ocr_run_id"),
        "oracle_ocr_run_id": oracle.get("ocr_run_id"),
        "oracle_sha256": sha256(sample.oracle_ocr),
    }
    for key, expected_value in expected_qa.items():
        if qa.get(key) != expected_value:
            errors.append(f"Oracle QA {key} does not match artifact")

    real_block_ids = {block["block_id"] for block in real.get("blocks", [])}
    oracle_block_ids = {
        block["block_id"] for block in oracle.get("blocks", [])
    }
    for category, findings in qa.get("real_vs_oracle_findings", {}).items():
        for index, finding in enumerate(findings):
            unknown_real = set(finding.get("real_block_ids", [])) - real_block_ids
            unknown_oracle = (
                set(finding.get("oracle_block_ids", [])) - oracle_block_ids
            )
            if unknown_real:
                errors.append(
                    f"Oracle QA {category}[{index}] has unknown Real block IDs"
                )
            if unknown_oracle:
                errors.append(
                    f"Oracle QA {category}[{index}] has unknown Oracle block IDs"
                )
    return errors


def sample_gate_errors(
    test_id: str,
    *,
    require_manifest_verified: bool = True,
) -> list[str]:
    """Return every reason one sample is not W3 gold-ready."""
    sample = paths_for(test_id)
    errors: list[str] = []
    required_before_adjudication = (
        sample.real_ocr,
        sample.oracle_ocr,
        sample.oracle_qa,
        sample.annotation_a,
        sample.annotation_b,
    )
    for path in required_before_adjudication:
        if not path.is_file():
            errors.append(f"missing file: {_relative(path)}")
    if errors:
        return errors
    final_missing = not sample.final_annotation.is_file()
    if final_missing:
        errors.append(f"missing file: {_relative(sample.final_annotation)}")

    real = load_json(sample.real_ocr)
    oracle = load_json(sample.oracle_ocr)
    try:
        validate_ocr_result(real)
    except ValueError as exc:
        errors.append(f"invalid Real OCR: {exc}")
    try:
        validate_ocr_result(oracle)
    except ValueError as exc:
        errors.append(f"invalid Oracle OCR: {exc}")
    if real.get("receipt_id") != oracle.get("receipt_id"):
        errors.append("Real and Oracle receipt_id differ")
    if real.get("ocr_run_id") == oracle.get("ocr_run_id"):
        errors.append("Real and Oracle ocr_run_id must be distinct")
    oracle_confidences = [
        float(block["confidence"])
        for block in oracle.get("blocks", [])
        if isinstance(block, dict) and "confidence" in block
    ]
    expected_average = (
        round(sum(oracle_confidences) / len(oracle_confidences), 6)
        if oracle_confidences
        else 0.0
    )
    if oracle.get("average_confidence") != expected_average:
        errors.append(
            "Oracle average_confidence must equal the mean block confidence"
        )

    a = load_json(sample.annotation_a)
    b = load_json(sample.annotation_b)
    annotation_error_sets: dict[str, list[str]] = {}
    for label, annotation in (("A", a), ("B", b)):
        component_errors = annotation_errors(annotation, real)
        annotation_error_sets[label] = component_errors
        errors.extend(
            f"annotation {label}: {error}"
            for error in component_errors
        )
    if a.get("annotator_id") == b.get("annotator_id"):
        errors.append("annotator A and B must be different")
    errors.extend(_oracle_qa_errors(test_id, sample, real, oracle))
    ab_has_valid_shape = not any(annotation_error_sets.values())
    expected_disagreements = (
        set(disagreement_fields(a, b)) if ab_has_valid_shape else set()
    )
    adjudication_missing = bool(expected_disagreements) and not (
        sample.adjudication.is_file()
    )
    if adjudication_missing:
        errors.append(f"missing file: {_relative(sample.adjudication)}")
    if final_missing or adjudication_missing:
        return errors

    final = load_json(sample.final_annotation)
    final_errors = annotation_errors(final, real)
    annotation_error_sets["final"] = final_errors
    errors.extend(f"annotation final: {error}" for error in final_errors)

    annotations_have_shape = not any(annotation_error_sets.values())
    disagreements = expected_disagreements if annotations_have_shape else set()
    adjudication: dict[str, Any] | None = None
    if disagreements:
        adjudication = load_json(sample.adjudication)
        errors.extend(
            f"adjudication: {error}"
            for error in schema_errors(adjudication, ADJUDICATION_SCHEMA_PATH)
        )
        expected_adjudication_ids = {
            "test_id": test_id,
            "receipt_id": real.get("receipt_id"),
            "source_ocr_run_id": real.get("ocr_run_id"),
            "annotation_a_id": a.get("annotation_id"),
            "annotation_b_id": b.get("annotation_id"),
        }
        for key, expected_value in expected_adjudication_ids.items():
            if adjudication.get(key) != expected_value:
                errors.append(
                    f"adjudication {key} does not match source records"
                )
        if adjudication.get("adjudicator_id") in {
            a.get("annotator_id"),
            b.get("annotator_id"),
        }:
            errors.append("adjudicator must differ from annotator A and B")
        recorded = set(adjudication.get("disagreements", {}))
        if disagreements != recorded:
            errors.append(
                "adjudication disagreement fields do not match A/B comparison"
            )
    for field_name in FIELD_NAMES if annotations_have_shape else ():
        final_label = semantic_label(final.get("fields", {}).get(field_name, {}))
        if field_name not in disagreements:
            if final_label != semantic_label(a["fields"][field_name]):
                errors.append(f"{field_name}: final differs from agreed A/B label")
            continue
        if adjudication is None:
            errors.append(f"{field_name}: missing adjudication decision")
            continue
        decision = adjudication.get("disagreements", {}).get(field_name, {})
        if decision.get("annotation_a") != semantic_label(a["fields"][field_name]):
            errors.append(f"{field_name}: adjudication A snapshot mismatch")
        if decision.get("annotation_b") != semantic_label(b["fields"][field_name]):
            errors.append(f"{field_name}: adjudication B snapshot mismatch")
        if decision.get("final") != final_label:
            errors.append(f"{field_name}: adjudication final snapshot mismatch")

    manifest, records = _manifest_by_id()
    record = records.get(test_id)
    if record is None:
        errors.append("sample is missing from evaluation manifest")
    else:
        if require_manifest_verified:
            if record.get("oracle_qa_state") != "VERIFIED":
                errors.append("manifest oracle_qa_state is not VERIFIED")
            if not record.get("oracle_provenance"):
                errors.append("manifest oracle_provenance is missing")
    if require_manifest_verified:
        if manifest.get("annotation_qa_state") != "VERIFIED":
            errors.append("manifest annotation_qa_state is not VERIFIED")
        if not manifest.get("annotation_provenance"):
            errors.append("manifest annotation_provenance is missing")
    return errors


def promote_verified_manifest(annotation_provenance: str) -> dict[str, Any]:
    """Promote only after every explicit human QA record passes the gate."""
    if not annotation_provenance.strip():
        raise ValueError("annotation_provenance must be non-empty")
    failures: dict[str, list[str]] = {}
    for row in split_rows():
        test_id = row["test_id"]
        errors = sample_gate_errors(
            test_id,
            require_manifest_verified=False,
        )
        if errors:
            failures[test_id] = errors
    if failures:
        details = "\n".join(
            f"{test_id}: " + "; ".join(errors)
            for test_id, errors in failures.items()
        )
        raise ValueError("Human QA artifacts are incomplete:\n" + details)

    manifest, records = _manifest_by_id()
    expected_ids = [row["test_id"] for row in split_rows()]
    if list(records) != expected_ids:
        raise ValueError("Manifest must contain ordered R001-R040 before promotion")
    for test_id in expected_ids:
        qa = load_json(paths_for(test_id).oracle_qa)
        records[test_id]["oracle_qa_state"] = "VERIFIED"
        records[test_id]["oracle_provenance"] = qa["provenance"]
    manifest["annotation_qa_state"] = "VERIFIED"
    manifest["annotation_provenance"] = annotation_provenance.strip()
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return manifest


def workflow_status() -> dict[str, Any]:
    rows = split_rows()
    samples: dict[str, Any] = {}
    ready = 0
    for row in rows:
        test_id = row["test_id"]
        errors = sample_gate_errors(test_id)
        if not errors:
            ready += 1
        samples[test_id] = {"ready": not errors, "reasons": errors}
    return {
        "required": len(rows),
        "ready": ready,
        "pending": len(rows) - ready,
        "samples": samples,
    }
