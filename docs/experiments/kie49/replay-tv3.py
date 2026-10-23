"""Replay pinned TV3 development evidence only; no gold access or accuracy."""

import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ai.kie.v2 import extract_with_grouping  # noqa: E402 (standalone repo bootstrap)
from ai.kie.v2.config import GROUPING_CONFIGURATIONS  # noqa: E402
from ai.kie.v2.evaluation import implementation_digest  # noqa: E402
from backend.app.v2.contracts import validate_evidence, validate_result  # noqa: E402

archive = Path(sys.argv[1])
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=False)
sha = hashlib.sha256(archive.read_bytes()).hexdigest()
assert sha == "fac7081b93d9b5255f7c756c6fcc246e3a726807d3a7b7853ad47f9f79d97d8e"
report = {
    "scope": "TV3 saved evidence contract replay only; not rerunning OCR",
    "source_revision": "036b7754811b8c8ae45a96d4dac56550904666e2",
    "zip_sha256": sha,
    "implementation_sha256": implementation_digest(),
    "configurations": GROUPING_CONFIGURATIONS,
    "metrics": None,
    "samples": [],
    "failures": [],
}
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist()) == len(set(z.namelist()))
    base = PurePosixPath("results/dev/tv2-reader-v0/paired-20261023")
    handoff = json.loads(z.read(str(base / "handoff.json")))
    assert handoff["split"] == "validation"
    for sample in handoff["samples"]:
        try:
            assert sample["source_provenance"]["source_split"] == "validation"
            relative = PurePosixPath(sample["evidence_path"])
            assert not relative.is_absolute() and ".." not in relative.parts
            data = z.read(str(base / relative))
            assert hashlib.sha256(data).hexdigest() == sample["evidence_sha256"]
            evidence = json.loads(data)
            receipt, run = sample["receipt_id"], sample["ocr_run_id"]
            validate_evidence(evidence, receipt, run)
            kie_run = uuid5(UUID(run), "kie49-tv3-replay")
            row = {
                "sample_id": sample["id"],
                "mode": sample["mode"],
                "evidence_sha256": sample["evidence_sha256"],
                "variants": {},
            }
            for name in GROUPING_CONFIGURATIONS:
                result = extract_with_grouping(
                    evidence, kie_run_id=kie_run, grouping=name
                )
                validate_result(result, evidence, receipt, str(kie_run), run)
                filename = f"{sample['mode']}-{sample['id']}-{name}.json"
                assert Path(filename).name == filename
                data = (
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n"
                ).encode()
                (output / filename).write_bytes(data)
                row["variants"][name] = {
                    "path": filename,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "predicted_rows": len(result["line_items"]),
                }
            report["samples"].append(row)
        except Exception as exc:
            report["failures"].append(
                {"sample_id": sample["id"], "mode": sample["mode"], "reason": str(exc)}
            )
    report["required"] = len(handoff["samples"])
report["paired_success"] = len(report["samples"])
(output / "report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
)
print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2))
raise SystemExit(bool(report["failures"]))
