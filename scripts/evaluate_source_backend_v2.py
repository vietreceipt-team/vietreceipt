"""Gated original-file HTTP capture plus TV4 source metrics, without rerunning KIE."""

import argparse
import hashlib
import io
import json
import math
import re
import subprocess
from contextlib import closing
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from PIL import Image, ImageOps

from ai.kie.v2.config import GROUPING_CONFIGURATIONS
from ai.kie.v2.evaluation import VERSION, validate_gold
from ai.kie.v2.source_evaluation import (
    SOURCE_MATCHING_VERSION,
    source_metrics,
    validate_regions,
)
from scripts.backend_evaluation_reports import write_csv, write_json
from scripts.evaluate_backend_v2 import load_manifest, run

PROFILE = "normalized-top-left-canonical-1.0"
SCHEMA = "backend-source-evaluation-1.0"


class GateError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise GateError(code)


def stamp(value):
    try:
        return bool(datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo)
    except (ValueError, TypeError, AttributeError):
        return False


def artifact(base, reference):
    path = (base / reference["path"]).resolve()
    require(path.is_relative_to(base.resolve()), "ARTIFACT_PATH_ESCAPE")
    raw = path.read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == reference["sha256"], "ARTIFACT_HASH_MISMATCH"
    )
    return json.loads(raw)


def prepare(plan_path):
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "schemas/backend-source-evaluation.v1.schema.json"
        ).read_text()
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(plan)
    require(plan["schema_version"] == SCHEMA, "PLAN_VERSION")
    require(plan["split"] in ("train", "validation"), "FINAL_TEST_LOCKED")
    require(plan["authorized"] is True, "DATA_NOT_AUTHORIZED")
    require(
        plan["frozen"] is True
        and plan["qa_status"] == "VERIFIED"
        and stamp(plan["frozen_at"]),
        "WAITING_FOR_VERIFIED_SOURCE_GOLD",
    )
    protocol = plan["protocol"]
    require(
        protocol["evaluator_version"] == VERSION
        and protocol["matching_version"] == SOURCE_MATCHING_VERSION
        and protocol["coordinate_profile"] == PROFILE
        and protocol["scope"] == "13_headers+line_items_tax_excluded",
        "PROTOCOL_MISMATCH",
    )
    require(
        protocol["configuration"] in GROUPING_CONFIGURATIONS.values(),
        "CONFIGURATION_MISMATCH",
    )
    require(
        re.fullmatch(r"[0-9a-f]{64}", protocol["worker_source_sha256"])
        and stamp(protocol["approved_at"])
        and all(
            isinstance(protocol["approved_by"].get(role), str)
            and protocol["approved_by"][role].strip()
            for role in ("TV1", "TV2", "TV4", "TV5")
        ),
        "WAITING_FOR_PROTOCOL_SIGNOFF",
    )
    records = plan["records"]
    require(records and plan["sample_count"] == len(records), "COHORT_COUNT")
    registry = plan["split_registry"]
    require(
        registry and len({r["id"] for r in registry}) == len(registry),
        "DUPLICATE_REGISTRY_ID",
    )
    for key in ("base_document_id", "template_id", "source_sha256"):
        splits = {}
        for r in registry:
            require(
                isinstance(r[key], str) and bool(r[key].strip()),
                "MISSING_SPLIT_IDENTITY",
            )
            splits.setdefault(r[key], set()).add(r["split"])
        require(all(len(s) == 1 for s in splits.values()), "SPLIT_LEAKAGE")
    cohort = {r["id"]: r for r in registry if r["split"] == plan["split"]}
    require(
        len(cohort) == len(records) and {r["id"] for r in records} == set(cohort),
        "MISSING_OR_DUPLICATE_SAMPLE",
    )
    prepared = []
    for record in records:
        sid = record["id"]
        require(
            isinstance(sid, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", sid),
            "UNSAFE_SAMPLE_ID",
        )
        source = record["source"]
        require(
            re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
            and source["content_type"]
            in ("application/pdf", "image/png", "image/jpeg"),
            "INVALID_SOURCE_DECLARATION",
        )
        require(
            source["sha256"] == cohort[sid]["source_sha256"]
            and all(
                record[k] == cohort[sid][k] for k in ("base_document_id", "template_id")
            ),
            "SOURCE_COHORT_IDENTITY",
        )
        path = (plan_path.parent / source["path"]).resolve()
        require(path.is_relative_to(plan_path.parent.resolve()), "SOURCE_PATH_ESCAPE")
        qa = record["qa"]
        require(
            qa["status"] == "VERIFIED"
            and stamp(qa["reviewed_at"])
            and isinstance(qa["annotated_by"], str)
            and qa["annotated_by"].strip()
            and isinstance(qa["reviewed_by"], str)
            and qa["reviewed_by"].strip()
            and qa["annotated_by"].strip().casefold()
            != qa["reviewed_by"].strip().casefold(),
            "WAITING_FOR_INDEPENDENT_REVIEW",
        )
        require(
            qa["gold_sha256"] == record["gold"]["sha256"]
            and qa["regions_sha256"] == record["regions"]["sha256"]
            and qa["source_sha256"] == source["sha256"],
            "REVIEW_HASH_MISMATCH",
        )
        gold = artifact(plan_path.parent, record["gold"])
        regions = artifact(plan_path.parent, record["regions"])
        require(
            gold["sample_id"] == record["source_sample_id"]
            and gold["receipt_id"] == record["source_receipt_id"]
            and all(
                gold[k] == plan[k]
                for k in ("dataset_family", "dataset_snapshot", "split", "synthetic")
            ),
            "GOLD_IDENTITY",
        )
        validate_gold(gold, None, plan, aligned=False)
        validate_regions(regions, gold)
        frame = record["geometry"]
        sizes = frame["page_sizes"]
        require(
            frame["profile"] == PROFILE
            and sizes
            and all(
                len(size) == 2 and all(type(v) is int and v > 0 for v in size)
                for size in sizes
            ),
            "UNREVIEWED_COORDINATE_FRAME",
        )
        require(
            all(r["page_index"] < len(sizes) for r in regions), "REGION_PAGE_MISMATCH"
        )
        prepared.append((record, path, gold, regions))
    return plan, prepared


def geometry(data, mime, dpi):
    """Same canonical frames as TV3; reject other frames instead of guessing a transform."""
    if mime == "application/pdf":
        import pypdfium2 as pdfium

        sizes = []
        with pdfium.PdfDocument(data) as document:
            for index in range(len(document)):
                with closing(document[index]) as page:
                    page.set_rotation(0)
                    width, height = page.get_size()
                    sizes.append(
                        (math.ceil(width * dpi / 72), math.ceil(height * dpi / 72))
                    )
        return sizes
    with Image.open(io.BytesIO(data)) as image:
        transposed = ImageOps.exif_transpose(image)
        try:
            return [transposed.size]
        finally:
            transposed.close()


def selected_case(folder, row, record, path, protocol, gold, regions):
    if not row["processing_success"]:
        require(
            row["status"] == "failed" and row.get("error") and row["error"].get("code"),
            "UNEXPLAINED_PROCESSING_FAILURE",
        )
        if row["receipt_id"] and row["error"]["code"] != "PROCESSING_TIMEOUT":
            snapshot = json.loads(
                (folder / row["id"] / "machine/snapshot.json").read_text()
            )
            failed = [
                a
                for a in snapshot["attempts"]
                if a["status"] == "FAILED"
                and (a.get("error") or {}).get("code") == row["error"]["code"]
            ]
            require(
                snapshot["receipt_id"] == row["receipt_id"]
                and len(failed) == 1
                and not any(a["status"] == "SUCCEEDED" for a in snapshot["attempts"]),
                "FAILED_ATTEMPT_IDENTITY_MISMATCH",
            )
            provenance = failed[0]["provenance"]
            require(
                "source" in provenance
                and row["input_sha256"] == record["source"]["sha256"]
                and (
                    provenance["source"] is None
                    or provenance["source"]["sha256"] == record["source"]["sha256"]
                )
                and provenance["runtime"]["source_sha256"]
                == protocol["worker_source_sha256"],
                "FAILED_SOURCE_IDENTITY_MISMATCH",
            )
        return None, gold, None, regions
    raw = path.read_bytes()
    require(
        hashlib.sha256(raw).hexdigest()
        == record["source"]["sha256"]
        == row["input_sha256"],
        "SOURCE_HASH_MISMATCH",
    )
    snapshot = json.loads((folder / row["id"] / "machine/snapshot.json").read_text())
    processing = json.loads((folder / row["id"] / "processing.json").read_text())
    rid = row["receipt_id"]
    require(
        rid == snapshot["receipt_id"] == processing["receipt_id"],
        "RECEIPT_IDENTITY_MISMATCH",
    )
    attempts = [
        a
        for a in snapshot["attempts"]
        if a["status"] == "SUCCEEDED"
        and a["kie_run_id"] == processing["latest_kie_run_id"]
    ]
    require(len(attempts) == 1, "SELECTED_ATTEMPT_MISMATCH")
    attempt = attempts[0]
    provenance = attempt["provenance"]
    require(
        provenance["source"]["sha256"] == row["input_sha256"]
        and provenance["source"]["content_type"] == record["source"]["content_type"],
        "WORKER_SOURCE_MISMATCH",
    )
    config = provenance["config"]
    require(
        config["providers"]
        == {
            "V2_DOCUMENT_READER_CALLABLE": "ai.document_reader.backend:read_document",
            "V2_KIE_CALLABLE": "ai.kie.v2:extract_invoice",
        }
        and config["callables"]
        == {
            "reader": "backend.app.v2.providers:configured_reader",
            "kie": "backend.app.v2.providers:configured_kie",
        },
        "NONCANONICAL_PROVIDERS",
    )
    require(
        provenance["runtime"]["source_sha256"] == protocol["worker_source_sha256"],
        "WORKER_IMPLEMENTATION_MISMATCH",
    )
    require(
        config["kie_configuration"] == protocol["configuration"],
        "WORKER_CONFIGURATION_MISMATCH",
    )
    chosen = {}
    for kind, run_key in (("OCR", "ocr_run_id"), ("KIE", "kie_run_id")):
        runs = [
            r
            for r in snapshot["runs"]
            if r["kind"] == kind
            and r["run_id"] == attempt[run_key]
            and r["attempt_id"] == attempt["attempt_id"]
        ]
        require(len(runs) == 1, "MACHINE_RUN_LINK_MISMATCH")
        chosen[kind] = runs[0]
    evidence, result = chosen["OCR"]["payload"], chosen["KIE"]["payload"]
    require(
        result["receipt_id"] == evidence["receipt_id"] == rid
        and result["source_ocr_run_id"]
        == evidence["ocr_run_id"]
        == attempt["ocr_run_id"]
        and result["kie_run_id"] == attempt["kie_run_id"]
        and chosen["KIE"]["source_ocr_run_id"] == attempt["ocr_run_id"],
        "PAYLOAD_IDENTITY_MISMATCH",
    )
    require(
        result["configuration"] == protocol["configuration"],
        "RESULT_CONFIGURATION_MISMATCH",
    )
    require(
        config["reader"] == protocol["reader_configuration"],
        "READER_CONFIGURATION_MISMATCH",
    )
    sizes = geometry(raw, record["source"]["content_type"], config["reader"]["dpi"])
    require(
        [list(size) for size in sizes] == record["geometry"]["page_sizes"],
        "REVIEWED_GEOMETRY_MISMATCH",
    )
    pages = evidence.get("pages", [{"page_index": 0, "evidence": evidence}])
    require(len(pages) == len(sizes), "PAGE_COUNT_MISMATCH")
    for page, size in zip(pages, sizes):
        image = page["evidence"]["image"]
        require(
            (image["width_px"], image["height_px"]) == size, "COORDINATE_FRAME_MISMATCH"
        )
    require(all(r["page_index"] < len(sizes) for r in regions), "REGION_PAGE_MISMATCH")
    return result, gold, evidence, regions


def score(plan_path, capture, output):
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        status="WAITING_FOR_VERIFIED_SOURCE_GOLD",
        metrics=None,
        evaluated=0,
        schema_version=SCHEMA,
        evaluator_version=VERSION,
        matching_version=SOURCE_MATCHING_VERSION,
        coordinate_profile=PROFILE,
        scope="13_headers+line_items_tax_excluded",
        reasons=[],
    )
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True
    )
    report["scorer"] = dict(
        commit=commit.stdout.strip() or None,
        dirty=bool(dirty.stdout.strip()),
        source_sha256={
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in (
                "scripts/evaluate_source_backend_v2.py",
                "ai/kie/v2/source_evaluation.py",
                "ai/kie/v2/evaluation.py",
                "schemas/backend-source-evaluation.v1.schema.json",
            )
        },
    )
    try:
        plan, prepared = prepare(plan_path.resolve())
        report["plan_sha256"] = hashlib.sha256(plan_path.read_bytes()).hexdigest()
        manifest = load_manifest(capture / "manifest.json")
        run_meta = json.loads((capture / "run.json").read_text())
        require(run_meta["mode"] == "real", "TEST_PROVIDERS_NOT_ACCURACY")
        require(
            run_meta["manifest_sha256"]
            == hashlib.sha256((capture / "manifest.json").read_bytes()).hexdigest(),
            "CAPTURE_MANIFEST_CHANGED",
        )
        require(
            (
                manifest["dataset"],
                manifest["version"],
                manifest["split"],
                manifest["synthetic"],
            )
            == (
                plan["dataset_family"],
                plan["dataset_snapshot"],
                plan["split"],
                plan["synthetic"],
            ),
            "CAPTURE_DATASET_MISMATCH",
        )
        require(
            [s["id"] for s in manifest["samples"]] == [r[0]["id"] for r in prepared],
            "CAPTURE_COHORT_MISMATCH",
        )
        consumed = [capture / "manifest.json", capture / "run.json"]
        consumed += [capture / r[0]["id"] / "result.json" for r in prepared]
        consumed += [
            p
            for r in prepared
            for p in (
                capture / r[0]["id"] / "processing.json",
                capture / r[0]["id"] / "machine/snapshot.json",
            )
            if p.exists()
        ]
        fingerprints = {
            str(p.relative_to(capture)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in consumed
        }
        cases, rows = [], []
        for sample, (record, path, gold, regions) in zip(manifest["samples"], prepared):
            require(
                sample["sha256"] == record["source"]["sha256"],
                "CAPTURE_SOURCE_HASH_MISMATCH",
            )
            row = json.loads((capture / record["id"] / "result.json").read_text())
            require(row["id"] == record["id"], "RESULT_SAMPLE_MISMATCH")
            cases.append(
                selected_case(
                    capture, row, record, path, plan["protocol"], gold, regions
                )
            )
            rows.append(row)
        measured = source_metrics(cases)
        require(
            all(
                hashlib.sha256((capture / name).read_bytes()).hexdigest() == digest
                for name, digest in fingerprints.items()
            ),
            "CAPTURE_CHANGED_DURING_SCORING",
        )
        report["capture_files_sha256"] = fingerprints
        write_csv(
            output / "failures.csv",
            [
                dict(
                    sample_id=r["id"],
                    stage=r["error"]["stage"],
                    code=r["error"]["code"],
                    total_ms=r["total_ms"],
                )
                for r in rows
                if r.get("error")
            ],
            ["sample_id", "stage", "code", "total_ms"],
        )
        per_sample = [
            dict(
                id=r["id"],
                processing_success=r["processing_success"],
                metrics=source_metrics([case]),
            )
            for r, case in zip(rows, cases)
        ]
        write_json(output / "samples.json", per_sample)
        write_csv(
            output / "samples.csv",
            [
                dict(
                    sample_id=r["id"],
                    processing_success=r["processing_success"],
                    complete_invoice_accuracy=r["metrics"]["complete_invoice_accuracy"],
                    row_precision=r["metrics"]["lines"]["detection_precision"],
                    row_recall=r["metrics"]["lines"]["detection_recall"],
                    row_f1=r["metrics"]["lines"]["detection_f1"],
                )
                for r in per_sample
            ],
            [
                "sample_id",
                "processing_success",
                "complete_invoice_accuracy",
                "row_precision",
                "row_recall",
                "row_f1",
            ],
        )
        report.update(
            status="COMPLETED_DEVELOPMENT_SOURCE_EVALUATION",
            metrics=measured,
            evaluated=len(cases),
            result_scope="synthetic_development_diagnostic"
            if plan["synthetic"]
            else "authorized_development_evaluation",
            capture_runner=run_meta,
            approvals=plan["protocol"]["approved_by"],
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ValidationError,
    ) as exc:
        report["reasons"].append(
            str(exc)
            if isinstance(exc, GateError)
            else "INVALID_OR_MISSING_INPUT_ARTIFACT"
        )
    write_json(output / "report.json", report)
    return report


def execute(plan_path, output, url):
    """One command: gate all gold first, then upload fresh files and score raw results."""
    try:
        plan, prepared = prepare(plan_path.resolve())
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ValidationError):
        return score(plan_path, output / "unstarted-capture", output)
    plan_digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir()
    manifest = dict(
        dataset=plan["dataset_family"],
        version=plan["dataset_snapshot"],
        split=plan["split"],
        synthetic=plan["synthetic"],
        samples=[
            dict(
                id=r["id"],
                path=str(path),
                sha256=r["source"]["sha256"],
                content_type=r["source"]["content_type"],
            )
            for r, path, _, _ in prepared
        ],
    )
    write_json(inputs / "manifest.json", manifest)
    run(inputs / "manifest.json", output / "capture", url=url, mode="real")
    if hashlib.sha256(plan_path.read_bytes()).hexdigest() != plan_digest:
        result = dict(
            status="WAITING_FOR_VERIFIED_SOURCE_GOLD",
            metrics=None,
            evaluated=0,
            reasons=["PLAN_CHANGED_DURING_CAPTURE"],
        )
        write_json(output / "report.json", result)
        return result
    return score(plan_path, output / "capture", output / "source-evaluation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument(
        "--capture",
        type=Path,
        help="Score an existing raw capture without HTTP or rerunning KIE",
    )
    args = parser.parse_args()
    result = (
        score(args.plan, args.capture, args.output)
        if args.capture
        else execute(args.plan, args.output, args.url)
    )
    return 0 if result["metrics"] is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
