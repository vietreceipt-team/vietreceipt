import json
import subprocess
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.v2.errors import V2Error
from backend.app.v2.processing import Processor
from backend.app.v2.providers import configured_kie, configured_reader
from backend.app.v2.reader_isolation import read_isolated
from scripts.evaluate_backend_v2 import run
from test_workflow import image_bytes, kie, reader, process


def test_machine_snapshot_never_contains_review_overlay(svc):
    detail = process(svc)
    rid = detail["receipt_id"]
    client = TestClient(create_app(v2_service=svc))
    original = client.get(f"/api/v2/receipts/{rid}/machine-results").json()
    assert {r["kind"] for r in original["runs"]} == {"OCR", "KIE"}
    provenance = original["attempts"][0]["provenance"]
    assert provenance["runtime"]["source_sha256"]
    assert provenance["timing_ms"]["kie"] >= 0
    assert provenance["timing_ms"]["document_reading"] >= 0
    assert "DATABASE_URL" not in json.dumps(provenance)
    svc.correct(
        rid, "header", "", "invoice_number", "HUMAN-ONLY", "PRESENT", detail["version"]
    )
    assert client.get(f"/api/v2/receipts/{rid}/machine-results").json() == original
    assert "HUMAN-ONLY" not in json.dumps(original)
    assert client.get(f"/api/v2/receipts/{uuid4()}/machine-results").status_code == 404


@pytest.mark.parametrize(
    "failure, code",
    [("crash", "DOCUMENT_READER_CRASHED"), ("timeout", "DOCUMENT_READER_TIMEOUT")],
)
def test_reader_native_failure_becomes_failed_attempt_and_can_retry(
    svc, monkeypatch, failure, code
):
    import backend.app.v2.reader_isolation as isolation

    monkeypatch.setenv("V2_READER_ISOLATION", "subprocess")

    original_run = isolation.subprocess.run

    def child(*args, **kwargs):
        if "backend.app.v2.reader_process" not in args[0]:
            return original_run(*args, **kwargs)
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args[0], 1)
        return subprocess.CompletedProcess(args[0], -11)

    monkeypatch.setattr(isolation.subprocess, "run", child)
    detail = svc.upload("photo.jpg", "image/jpeg", image_bytes("JPEG"))
    rid = detail["receipt_id"]
    assert not Processor(svc, configured_reader, configured_kie).process(rid)
    detail = svc.detail(rid)
    assert detail["status"] == "FAILED"
    assert detail["processing_error"]["code"] == code
    assert detail["processing_error"]["retryable"]
    assert detail["latest_ocr_run_id"] is None
    assert not detail["fields"]
    svc.retry(rid, detail["version"])
    assert Processor(svc, reader, kie).process(rid)
    snapshot = (
        TestClient(create_app(v2_service=svc))
        .get(f"/api/v2/receipts/{rid}/machine-results")
        .json()
    )
    assert [a["status"] for a in snapshot["attempts"]] == ["FAILED", "SUCCEEDED"]


@pytest.mark.parametrize("timeout", ["0", "nan", "inf", "801", "bad"])
def test_invalid_timeout_fails_before_child(monkeypatch, timeout):
    monkeypatch.setenv("V2_READER_TIMEOUT_SECONDS", timeout)
    with pytest.raises(V2Error) as error:
        read_isolated(
            b"x",
            content_type="image/jpeg",
            receipt_id=str(uuid4()),
            ocr_run_id=str(uuid4()),
        )
    assert error.value.code == "INVALID_READER_CONFIG"
    assert not error.value.retryable


class ProcessingClient(TestClient):
    def __init__(self, svc, fail=False):
        super().__init__(create_app(v2_service=svc))
        self.svc, self.fail = svc, fail

    def post(self, url, **kwargs):
        response = super().post(url, **kwargs)
        if url == "/api/v2/receipts" and response.status_code == 201 and not self.fail:
            Processor(self.svc, reader, kie).process(response.json()["receipt_id"])
        return response


def manifest(tmp_path):
    path = tmp_path / "photo.jpg"
    path.write_bytes(image_bytes("JPEG"))
    data = dict(
        dataset="test-only",
        version="1",
        split="demo",
        synthetic=True,
        samples=[
            dict(
                id="jpg",
                path=path.name,
                review={"header": {"invoice_number": "REVIEWED-ONLY"}},
            )
        ],
    )
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps(data))
    return source, data


def test_runner_separates_raw_corrected_exports_and_refuses_overwrite(svc, tmp_path):
    source, data = manifest(tmp_path)
    output = tmp_path / "result"
    rows = run(
        source,
        output,
        url="http://test",
        poll_interval=0,
        review=True,
        mode="test",
        client=ProcessingClient(svc),
    )
    assert rows[0]["status"] == "verified", rows
    assert set(rows[0]["exports"]) == {"json", "csv", "xlsx"}
    raw = (output / "jpg/machine/snapshot.json").read_text()
    assert "REVIEWED-ONLY" not in raw
    assert "REVIEWED-ONLY" in (output / "jpg/reviewed/export.json").read_text()
    assert json.loads((output / "run.json").read_text())["runner_commit"]
    with pytest.raises(FileExistsError):
        run(source, output, url="http://test", client=ProcessingClient(svc))
    with pytest.raises(ValueError):
        data["synthetic"] = False
        source.write_text(json.dumps(data))
        run(source, tmp_path / "unsafe", url="http://test", review=True)


def test_runner_keeps_timeouts_and_missing_inputs_in_denominator(svc, tmp_path):
    source, data = manifest(tmp_path)
    data["samples"].append(dict(id="missing", path="absent.pdf"))
    source.write_text(json.dumps(data))
    output = tmp_path / "result"
    rows = run(
        source,
        output,
        url="http://test",
        timeout=0.01,
        poll_interval=0.01,
        mode="test",
        client=ProcessingClient(svc, fail=True),
    )
    assert len(rows) == 2 and all(r["status"] == "failed" for r in rows)
    assert rows[0]["receipt_id"]
    assert (output / "jpg/machine/snapshot.json").exists()
    assert json.loads((output / "summary.json").read_text())["failed"] == 2


def test_manifest_hash_mismatch_does_not_upload(svc, tmp_path):
    source, data = manifest(tmp_path)
    data["samples"][0]["sha256"] = "0" * 64
    source.write_text(json.dumps(data))
    rows = run(
        source, tmp_path / "result", url="http://test", client=ProcessingClient(svc)
    )
    assert rows[0]["status"] == "failed" and rows[0]["receipt_id"] is None
    assert svc.list(10, 0) == []


def test_real_runner_rejects_injected_test_provider(svc, tmp_path):
    source, data = manifest(tmp_path)
    rows = run(
        source,
        tmp_path / "result",
        url="http://test",
        poll_interval=0,
        mode="real",
        client=ProcessingClient(svc),
    )
    assert rows[0]["status"] == "failed"
    assert "canonical TV3/TV4 providers" in rows[0]["error"]["message"]
