"""Synthetic software acceptance; approval identities below are test doubles only."""

import copy
import hashlib
import json
from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from ai.document_reader import ReaderConfig
from ai.kie.v2.config import CONFIGURATION, LINE_FIELDS
from ai.kie.v2.evaluation import VERSION
from ai.kie.v2.source_evaluation import SOURCE_MATCHING_VERSION
from backend.app.main import create_app
from backend.app.v2.processing import Processor
from backend.app.v2.providers import configured_kie, configured_reader
from scripts.backend_evaluation_reports import write_json
from scripts.evaluate_backend_v2 import run
from scripts.evaluate_source_backend_v2 import PROFILE, SCHEMA, execute, geometry, score
from tests.test_kie_v2_reader import reader_case


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RealPdfClient(TestClient):
    def __init__(self, svc):
        super().__init__(create_app(v2_service=svc))
        self.svc = svc

    def post(self, url, **kwargs):
        response = super().post(url, **kwargs)
        if url == "/api/v2/receipts" and response.status_code == 201:
            Processor(self.svc, configured_reader, configured_kie).process(
                response.json()["receipt_id"]
            )
        return response


@pytest.fixture
def accepted(tmp_path, svc, monkeypatch):
    monkeypatch.delenv("V2_DOCUMENT_READER_CALLABLE", raising=False)
    monkeypatch.delenv("V2_KIE_CALLABLE", raising=False)
    pdf, _, _, aligned_gold = reader_case()
    gold = copy.deepcopy(aligned_gold)
    for cell in list(gold["fields"].values()) + [
        r[f] for r in gold["line_items"] for f in LINE_FIELDS
    ]:
        cell["source_block_ids"] = []
    # Independent printed source locations, not locations copied from predictions.
    regions = [
        dict(
            line_id="independent-source-row-0",
            page_index=0,
            bounds=[0.05, 0.20, 0.98, 0.26],
        ),
        dict(
            line_id="independent-source-row-1",
            page_index=0,
            bounds=[0.05, 0.27, 0.98, 0.30],
        ),
    ]
    (tmp_path / "source.pdf").write_bytes(pdf)
    write_json(tmp_path / "gold.json", gold)
    write_json(tmp_path / "regions.json", regions)
    sid = "source01"
    manifest = dict(
        dataset=gold["dataset_family"],
        version=gold["dataset_snapshot"],
        split="validation",
        synthetic=True,
        samples=[dict(id=sid, path="source.pdf", sha256=sha(tmp_path / "source.pdf"))],
    )
    write_json(tmp_path / "manifest.json", manifest)
    capture = tmp_path / "capture"
    rows = run(
        tmp_path / "manifest.json",
        capture,
        url="http://test",
        mode="real",
        poll_interval=0,
        client=RealPdfClient(svc),
    )
    assert rows[0]["processing_success"], rows
    snapshot = load(capture / sid / "machine/snapshot.json")
    worker = snapshot["attempts"][0]["provenance"]
    original = worker["source"]
    assert original["sha256"] == sha(tmp_path / "source.pdf") and original[
        "bytes"
    ] == len(pdf)
    record = dict(
        id=sid,
        source_sample_id=gold["sample_id"],
        source_receipt_id=gold["receipt_id"],
        base_document_id="base1",
        template_id="template1",
        source=dict(
            path="source.pdf",
            sha256=sha(tmp_path / "source.pdf"),
            content_type="application/pdf",
        ),
        gold=dict(path="gold.json", sha256=sha(tmp_path / "gold.json")),
        regions=dict(path="regions.json", sha256=sha(tmp_path / "regions.json")),
        geometry=dict(
            profile=PROFILE, page_sizes=geometry(pdf, "application/pdf", 200)
        ),
        qa=dict(
            status="VERIFIED",
            annotated_by="test-author",
            reviewed_by="independent-test-reviewer",
            reviewed_at="2026-10-23T00:00:00Z",
            source_sha256=sha(tmp_path / "source.pdf"),
            gold_sha256=sha(tmp_path / "gold.json"),
            regions_sha256=sha(tmp_path / "regions.json"),
        ),
    )
    plan = dict(
        schema_version=SCHEMA,
        dataset_family=gold["dataset_family"],
        dataset_snapshot=gold["dataset_snapshot"],
        split="validation",
        synthetic=True,
        authorized=True,
        sample_count=1,
        frozen=True,
        frozen_at="2026-10-23T00:00:00Z",
        qa_status="VERIFIED",
        protocol=dict(
            evaluator_version=VERSION,
            matching_version=SOURCE_MATCHING_VERSION,
            coordinate_profile=PROFILE,
            scope="13_headers+line_items_tax_excluded",
            configuration=CONFIGURATION,
            reader_configuration=asdict(ReaderConfig()),
            worker_source_sha256=worker["runtime"]["source_sha256"],
            approved_at="2026-10-23T00:00:00Z",
            approved_by={
                role: "test-double-" + role for role in ("TV1", "TV2", "TV4", "TV5")
            },
        ),
        records=[record],
        split_registry=[
            dict(
                id=sid,
                base_document_id="base1",
                template_id="template1",
                source_sha256=record["source"]["sha256"],
                split="validation",
            )
        ],
    )
    path = tmp_path / "plan.json"
    write_json(path, plan)
    return path, capture, plan


def test_real_pdf_raw_prediction_to_spatial_metrics_and_unknown_coverage(
    accepted, tmp_path
):
    path, capture, _ = accepted
    before = {str(p): p.read_bytes() for p in capture.rglob("*") if p.is_file()}
    result = score(path, capture, tmp_path / "score")
    assert result["status"] == "COMPLETED_DEVELOPMENT_SOURCE_EVALUATION", result
    assert result["metrics"]["lines"]["detection_f1"] == 1
    assert result["metrics"]["lines"]["complete_line_accuracy"] == 1
    assert result["metrics"]["complete_invoice_accuracy"] is None
    assert result["metrics"]["header_coverage"]["unknown"] == 12
    assert before == {str(p): p.read_bytes() for p in capture.rglob("*") if p.is_file()}
    assert (tmp_path / "score/samples.csv").exists()


@pytest.mark.parametrize(
    "problem",
    [
        "qa",
        "reviewer",
        "review_hash",
        "protocol",
        "worker_hash",
        "geometry",
        "receipt",
        "ocr_link",
        "source_hash",
        "config",
        "missing_sample",
        "leak",
        "final",
        "test_provider",
        "gold_ocr_ids",
    ],
)
def test_fail_closed_bindings(accepted, tmp_path, problem):
    path, capture, plan = accepted
    record = plan["records"][0]
    snap_path = capture / "source01/machine/snapshot.json"
    snap = load(snap_path)
    if problem == "qa":
        plan["qa_status"] = "PENDING_REVIEW"
    elif problem == "reviewer":
        record["qa"]["reviewed_by"] = record["qa"]["annotated_by"]
    elif problem == "review_hash":
        record["qa"]["gold_sha256"] = "0" * 64
    elif problem == "protocol":
        plan["protocol"]["approved_by"]["TV1"] = None
    elif problem == "worker_hash":
        plan["protocol"]["worker_source_sha256"] = "0" * 64
    elif problem == "geometry":
        record["geometry"]["page_sizes"][0] = [
            record["geometry"]["page_sizes"][0][0] + 1,
            record["geometry"]["page_sizes"][0][1],
        ]
    elif problem == "receipt":
        snap["receipt_id"] = "another-receipt"
    elif problem == "ocr_link":
        snap["attempts"][0]["ocr_run_id"] = "another-run"
    elif problem == "source_hash":
        snap["attempts"][0]["provenance"]["source"]["sha256"] = "0" * 64
    elif problem == "config":
        plan["protocol"]["configuration"] = {
            "name": "invoice-column-intervals",
            "version": "2.2.0",
        }
    elif problem == "missing_sample":
        (capture / "source01/result.json").unlink()
    elif problem == "leak":
        plan["split_registry"].append(
            {**plan["split_registry"][0], "id": "train2", "split": "train"}
        )
    elif problem == "final":
        plan["split"] = "test"
    elif problem == "test_provider":
        meta = load(capture / "run.json")
        meta["mode"] = "test"
        write_json(capture / "run.json", meta)
    elif problem == "gold_ocr_ids":
        gold = load(tmp_path / "gold.json")
        gold["fields"]["currency"]["source_block_ids"] = ["p0_b1"]
        write_json(tmp_path / "gold.json", gold)
        record["gold"]["sha256"] = record["qa"]["gold_sha256"] = sha(
            tmp_path / "gold.json"
        )
    write_json(snap_path, snap)
    write_json(path, plan)
    result = score(path, capture, tmp_path / "score")
    assert result["metrics"] is None and result["evaluated"] == 0, result
    assert result["reasons"]


def test_failed_eligible_source_remains_in_denominator(
    accepted, tmp_path, svc, monkeypatch
):
    import ai.document_reader.backend as reader_backend
    from backend.app.v2.errors import V2Error

    path, _, _ = accepted

    def broken(*args, **kwargs):
        raise V2Error("DOCUMENT_READER_CRASHED", "synthetic failure", retryable=True)

    monkeypatch.setattr(reader_backend, "read_document", broken)
    capture = tmp_path / "failed-capture"
    rows = run(
        tmp_path / "manifest.json",
        capture,
        url="http://test",
        mode="real",
        poll_interval=0,
        client=RealPdfClient(svc),
    )
    assert not rows[0]["processing_success"]
    result = score(path, capture, tmp_path / "score")
    assert result["metrics"]["lines"]["failed_documents"] == 1, result
    assert result["metrics"]["lines"]["detection_recall"] == 0
    assert result["metrics"]["headers"]["currency"]["miss"] == 1
    assert result["metrics"]["complete_table_accuracy"] == 0


def test_success_snapshot_cannot_be_relabelled_as_failure(accepted, tmp_path):
    path, capture, _ = accepted
    row = load(capture / "source01/result.json")
    row.update(
        processing_success=False,
        status="failed",
        error={"code": "DOCUMENT_READER_CRASHED", "stage": "DOCUMENT_READING"},
    )
    write_json(capture / "source01/result.json", row)
    result = score(path, capture, tmp_path / "score")
    assert result["metrics"] is None
    assert "FAILED_ATTEMPT_IDENTITY_MISMATCH" in result["reasons"]


def test_pending_plan_never_uploads(accepted, tmp_path, monkeypatch):
    import scripts.evaluate_source_backend_v2 as module

    path, _, plan = accepted
    plan["qa_status"] = "PENDING_REVIEW"
    write_json(path, plan)

    def forbidden(*a, **kw):
        raise AssertionError("pending QA attempted HTTP")

    monkeypatch.setattr(module, "run", forbidden)
    result = execute(path, tmp_path / "pending", "http://test")
    assert result["metrics"] is None
    assert "WAITING_FOR_VERIFIED_SOURCE_GOLD" in result["reasons"]


def test_exif_display_coordinate_frame():
    import io

    from PIL import Image

    data = io.BytesIO()
    image = Image.new("RGB", (50, 30), "white")
    exif = image.getexif()
    exif[274] = 6
    image.save(data, format="JPEG", exif=exif)
    assert geometry(data.getvalue(), "image/jpeg", 200) == [(30, 50)]


def test_rotated_pdf_uses_canonical_unrotated_media_frame():
    import io

    from reportlab.pdfgen.canvas import Canvas

    data = io.BytesIO()
    canvas = Canvas(data, pagesize=(600, 800), invariant=1)
    canvas.setPageRotation(90)
    canvas.drawString(40, 400, "Currency: VND - canonical source coordinate check")
    canvas.save()
    # ReportLab's 90-degree page stores swapped media dimensions; undo display rotation.
    assert geometry(data.getvalue(), "application/pdf", 200) == [(2223, 1667)]


def test_worker_storage_read_failure_is_not_dropped(
    accepted, tmp_path, svc, monkeypatch
):
    path, _, _ = accepted

    def unreadable(*args):
        raise OSError("synthetic unavailable source storage")

    monkeypatch.setattr(svc, "source", unreadable)
    capture = tmp_path / "unreadable-capture"
    rows = run(
        tmp_path / "manifest.json",
        capture,
        url="http://test",
        mode="real",
        poll_interval=0,
        client=RealPdfClient(svc),
    )
    assert not rows[0]["processing_success"]
    result = score(path, capture, tmp_path / "score")
    assert result["metrics"]["lines"]["failed_documents"] == 1, result


def test_one_command_gate_capture_and_score(accepted, tmp_path, svc, monkeypatch):
    import scripts.evaluate_source_backend_v2 as module

    path, _, _ = accepted
    original_run = run

    def real_http_capture(manifest, output, **kwargs):
        return original_run(
            manifest, output, **kwargs, poll_interval=0, client=RealPdfClient(svc)
        )

    monkeypatch.setattr(module, "run", real_http_capture)
    result = execute(path, tmp_path / "one-command", "http://test")
    assert result["status"] == "COMPLETED_DEVELOPMENT_SOURCE_EVALUATION", result
    assert result["metrics"]["lines"]["detection_f1"] == 1


def test_expired_worker_without_prediction_remains_in_denominator(
    accepted, tmp_path, svc
):
    from backend.app.v2.processing import recover_expired

    path, _, _ = accepted

    class ExpiringClient(TestClient):
        def post(self, url, **kwargs):
            response = super().post(url, **kwargs)
            if url == "/api/v2/receipts" and response.status_code == 201:
                Processor(
                    svc, configured_reader, configured_kie, lease_seconds=1
                ).claim(response.json()["receipt_id"])
                import time

                recover_expired(svc, now=time.time() + 5)
            return response

    capture = tmp_path / "expired-capture"
    rows = run(
        tmp_path / "manifest.json",
        capture,
        url="http://test",
        mode="real",
        poll_interval=0,
        client=ExpiringClient(create_app(v2_service=svc)),
    )
    assert rows[0]["error"]["code"] == "WORKER_LEASE_EXPIRED"
    result = score(path, capture, tmp_path / "score")
    assert result["metrics"]["lines"]["failed_documents"] == 1, result
