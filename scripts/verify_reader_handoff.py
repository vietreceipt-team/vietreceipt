"""Check saved real Reader evidence with TV4/TV5, without rewriting any IDs."""

import argparse
import hashlib
from pathlib import Path
from uuid import uuid4

from ai.document_reader.contract import validate_document
from ai.kie.v2 import extract_invoice
from backend.app.v2.contracts import validate_evidence, validate_result
from scripts.benchmark_document_reader import dump
from scripts.compare_pdf_routes import read_json


def verify(run_dir, output):
    handoff = read_json(run_dir / "handoff.json")
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for sample in handoff["samples"]:
        path = (run_dir / sample["evidence_path"]).resolve()
        if not path.is_relative_to(run_dir.resolve()):
            raise ValueError("Evidence path escapes run directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != sample["evidence_sha256"]:
            raise ValueError("Evidence checksum mismatch")
        document = read_json(path)
        validate_document(document)
        receipt_id, ocr_run_id = document["receipt_id"], document["ocr_run_id"]
        if (receipt_id, ocr_run_id) != (sample["receipt_id"], sample["ocr_run_id"]):
            raise ValueError("Handoff identity mismatch")
        validate_evidence(document, receipt_id, ocr_run_id)
        kie_run_id = uuid4()
        result = extract_invoice(document, kie_run_id=kie_run_id)
        validate_result(result, document, receipt_id, str(kie_run_id), ocr_run_id)
        filename = f"{sample['mode']}-{sample['id']}.json"
        if Path(filename).name != filename:
            raise ValueError("Unsafe handoff sample name")
        dump(output / filename, result)
        rows.append({
            "id": sample["id"], "mode": sample["mode"], "receipt_id": receipt_id,
            "ocr_run_id": ocr_run_id, "kie_run_id": str(kie_run_id),
            "reader_contract": "pass", "tv5_evidence_contract": "pass",
            "tv4_kie_contract": "pass", "tv5_kie_contract": "pass",
            "kie_result": filename, "accuracy": None,
            "note": "Provider/schema check only; no independent gold or accuracy claim",
        })
    report = {"dataset": handoff["dataset"], "samples": rows,
              "gold_alignment": "pending_TV2_QA", "id_rewriting": False}
    dump(output / "verification.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.run_dir, args.output)
    print(f"Validated {len(report['samples'])} evidence/KIE runs; gold alignment still pending")


if __name__ == "__main__":
    main()
