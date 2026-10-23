"""Batch reporting and development handoff boundaries; no gold accuracy claims."""

import hashlib
import json

import httpx
import pytest
from test_reproducibility import ProcessingClient, manifest

from scripts.evaluate_backend_v2 import run
from scripts.prepare_tv2_backend_manifest import prepare


def read(path):
    return json.loads(path.read_text())


def test_batch_indexes_are_machine_only_and_keep_dataset_identity(svc, tmp_path):
    source, data = manifest(tmp_path)
    output = tmp_path / "run"
    run(
        source,
        output,
        url="http://test",
        client=ProcessingClient(svc),
        mode="test",
        review=True,
        poll_interval=0,
    )
    index = read_lines(output / "machine_predictions.jsonl")
    assert len(index) == 1 and index[0]["processing_success"]
    assert "REVIEWED-ONLY" not in (output / "machine_predictions.jsonl").read_text()
    assert {r["kind"] for r in index[0]["runs"]} == {"OCR", "KIE"}
    assert index[0]["attempts"][0]["provenance"]["timing_ms"]["kie"] >= 0
    report = read(output / "metrics.json")
    assert report["processing_success_rate"] == 1
    assert report["workflow_verified"] == 1
    assert report["accuracy"] is None
    metadata = read(output / "run_metadata.json")
    assert metadata["dataset"]["dataset"] == data["dataset"]
    assert metadata["runner_commit"] == read(output / "run.json")["runner_commit"]
    assert len((output / "failures.csv").read_text().splitlines()) == 1


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_failures_have_codes_stages_time_and_all_samples(svc, tmp_path):
    source, data = manifest(tmp_path)
    data["samples"].append(dict(id="missing", path="private-customer.pdf"))
    source.write_text(json.dumps(data))
    output = tmp_path / "run"
    rows = run(
        source,
        output,
        url="http://test",
        client=ProcessingClient(svc, fail=True),
        mode="test",
        timeout=0.01,
        poll_interval=0.01,
    )
    assert [r["error"]["code"] for r in rows] == [
        "PROCESSING_TIMEOUT",
        "INPUT_READ_FAILED",
    ]
    assert rows[0]["processing_wall_ms"] >= 0
    assert all(r["error"]["stage"] and r["total_ms"] >= 0 for r in rows)
    assert len(read_lines(output / "machine_predictions.jsonl")) == 2
    report = read(output / "metrics.json")
    assert report["expected_samples"] == report["processing_failed"] == 2
    assert report["processing_success_rate"] == 0
    assert len((output / "failures.csv").read_text().splitlines()) == 3
    assert "private-customer" not in (output / "failures.csv").read_text()
    assert "private-customer" not in json.dumps(rows)


def test_export_failure_does_not_become_machine_processing_failure(svc, tmp_path):
    class FailingExportClient(ProcessingClient):
        def get(self, url, **kwargs):
            if url.endswith("/export"):
                return httpx.Response(
                    500,
                    request=httpx.Request(
                        "GET", "http://user:secret@example.test/export?token=secret"
                    ),
                )
            return super().get(url, **kwargs)

    source, _ = manifest(tmp_path)
    output = tmp_path / "run"
    row = run(
        source,
        output,
        url="http://test",
        client=FailingExportClient(svc),
        mode="test",
        review=True,
        poll_interval=0,
    )[0]
    assert row["processing_success"] and row["status"] == "failed"
    assert row["error"]["stage"] == "EXPORT"
    assert "secret" not in json.dumps(row)
    assert read(output / "metrics.json")["processing_succeeded"] == 1
    assert read(output / "metrics.json")["workflow_failed"] == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_invalid_deadline_rejected_before_http(svc, tmp_path, value):
    source, _ = manifest(tmp_path)
    with pytest.raises(ValueError):
        run(
            source,
            tmp_path / "run",
            url="http://test",
            timeout=value,
            client=ProcessingClient(svc),
        )
    assert svc.list(10, 0) == []


def handoff(tmp_path):
    for split in ("train", "validation"):
        data = (split + " source bytes").encode()
        (tmp_path / (split + ".pdf")).write_bytes(data)
        record = dict(
            record_id=split,
            source=dict(path=split + ".pdf", sha256=hashlib.sha256(data).hexdigest()),
            split=split,
            final_eligible="false",
            qa_status="PENDING_REVIEW",
            base_document_id=split,
            template_id=split,
            source_type="text_pdf",
            augmentation_type="clean",
            reader_status="FAILED",
        )
        manifest_data = dict(
            schema_version="tv2-tv4-handoff-candidate-0.1",
            dataset_family="test",
            dataset_snapshot="1",
            split=split,
            synthetic=True,
            frozen=True,
            sample_count=1,
            freeze_scope="development membership only",
            qa_status="PENDING_REVIEW",
            records=[record],
        )
        (tmp_path / f"{split}-manifest.json").write_text(json.dumps(manifest_data))


def test_import_keeps_entire_validation_and_pending_qa(tmp_path):
    handoff(tmp_path)
    out = tmp_path / "out"
    result = prepare(tmp_path, out, "commit-test")
    assert len(result["samples"]) == 1
    assert result["samples"][0]["id"] == "validation"
    assert result["samples"][0]["qa_status"] == "PENDING_REVIEW"
    assert result["qa_status"] == "PENDING_REVIEW" and not result["accuracy_eligible"]
    assert (out / "validation.pdf").read_bytes() == (
        tmp_path / "validation.pdf"
    ).read_bytes()
    assert not (out / "train.pdf").exists()
    # Reader failure in TV2 does not remove the source from the backend cohort.
    assert result["provenance"]["base_documents"] == 1
    with pytest.raises(FileExistsError):
        prepare(tmp_path, out, "commit-test")


@pytest.mark.parametrize(
    "problem",
    [
        "split",
        "count",
        "hash",
        "parent_leak",
        "template_leak",
        "content_leak",
        "duplicate",
        "escape",
        "test",
        "missing_qa",
        "missing_freeze_scope",
    ],
)
def test_import_rejects_invalid_or_leaking_handoff_before_output(tmp_path, problem):
    handoff(tmp_path)
    path = tmp_path / "validation-manifest.json"
    data = read(path)
    row = data["records"][0]
    if problem == "split":
        row["split"] = "train"
    elif problem == "count":
        data["sample_count"] = 2
    elif problem == "hash":
        row["source"]["sha256"] = "0" * 64
    elif problem == "parent_leak":
        row["base_document_id"] = "train"
    elif problem == "template_leak":
        row["template_id"] = "train"
    elif problem == "content_leak":
        row["source"] = read(tmp_path / "train-manifest.json")["records"][0]["source"]
    elif problem == "duplicate":
        row["record_id"] = "train"
    elif problem == "escape":
        row["source"]["path"] = "../private.pdf"
    elif problem == "test":
        row["final_eligible"] = "true"
    elif problem == "missing_qa":
        data.pop("qa_status")
    elif problem == "missing_freeze_scope":
        data.pop("freeze_scope")
    path.write_text(json.dumps(data))
    with pytest.raises((ValueError, FileNotFoundError)):
        prepare(tmp_path, tmp_path / "out", "commit-test")
    assert not (tmp_path / "out").exists()


def test_pending_handoff_cannot_enable_automatic_review(svc, tmp_path):
    source, data = manifest(tmp_path)
    data["purpose"] = "development_workflow_capture_only"
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="machine capture only"):
        run(
            source,
            tmp_path / "run",
            url="http://test",
            review=True,
            client=ProcessingClient(svc),
        )


def test_worker_schema_error_is_reported_without_payload_text(svc, tmp_path):
    from backend.app.v2.errors import V2Error
    from backend.app.v2.processing import Processor

    class FailedReaderClient(ProcessingClient):
        def post(self, url, **kwargs):
            response = super(ProcessingClient, self).post(url, **kwargs)
            if url == "/api/v2/receipts" and response.status_code == 201:

                def failed_reader(*args, **kwargs):
                    raise V2Error(
                        "INVALID_OCR_OUTPUT",
                        "private receipt text and secret",
                        retryable=False,
                    )

                Processor(self.svc, failed_reader, lambda *_: None).process(
                    response.json()["receipt_id"]
                )
            return response

    source, _ = manifest(tmp_path)
    output = tmp_path / "run"
    row = run(
        source,
        output,
        url="http://test",
        client=FailedReaderClient(svc),
        mode="test",
        poll_interval=0,
    )[0]
    assert row["error"]["code"] == "INVALID_OCR_OUTPUT"
    assert row["error"]["stage"] == "DOCUMENT_READING"
    assert not row["processing_success"]
    assert "private receipt text" not in json.dumps(row)
    assert (
        read_lines(output / "machine_predictions.jsonl")[0]["attempts"][0]["status"]
        == "FAILED"
    )


def test_snapshot_detected_changed_after_review_is_not_overwritten(svc, tmp_path):
    class ChangedSnapshotClient(ProcessingClient):
        calls = 0

        def get(self, url, **kwargs):
            response = super().get(url, **kwargs)
            if url.endswith("/machine-results"):
                self.calls += 1
                if self.calls > 1:
                    data = response.json()
                    data["receipt_id"] = "CHANGED"
                    return httpx.Response(200, json=data, request=response.request)
            return response

    source, _ = manifest(tmp_path)
    output = tmp_path / "run"
    row = run(
        source,
        output,
        url="http://test",
        client=ChangedSnapshotClient(svc),
        mode="test",
        review=True,
        poll_interval=0,
    )[0]
    assert row["error"]["code"] == "MACHINE_SNAPSHOT_CHANGED"
    assert "CHANGED" not in (output / "jpg/machine/snapshot.json").read_text()
    assert "CHANGED" not in (output / "machine_predictions.jsonl").read_text()
