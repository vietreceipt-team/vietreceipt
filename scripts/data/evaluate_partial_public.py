"""Evaluate reviewed partial public gold without counting unsupported fields as errors.

Requires actual spatial evidence and saved canonical TV4 predictions. Never
links gold automatically or promotes development evaluation to final evidence.
"""

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from .common import HEADERS, LINE_FIELDS, ROOT, dump, sha


def evaluate(path):
    from ai.kie.v2.contract import validate_result
    from ai.kie.v2.evaluation import load_artifact, row_matches
    from ai.kie.v2.evidence import flatten

    path = Path(path)
    report = dict(
        status="WAITING",
        metrics=None,
        evaluated=0,
        reasons=[],
        evaluator_version="public-masked-0.1",
        result_scope="public_development_evaluation",
        executed_at=datetime.now(timezone.utc).isoformat(),
        manifest=str(path),
    )
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("purpose") != "development" or not manifest.get("records"):
            raise ValueError(
                "Explicit development manifest with reviewed records required"
            )
        for key in ("dataset_family", "dataset_snapshot", "split", "template_regime"):
            if not isinstance(manifest.get(key), str) or not manifest[key]:
                raise ValueError("Missing " + key)
            report[key] = manifest[key]
        report["manifest_sha256"] = sha(path)
        report["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        report["git_dirty"] = bool(
            subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        )
        schema = json.loads(
            (ROOT / "schemas/invoice-annotation.v2.schema.json").read_text()
        )
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        prepared = []
        receipts = set()
        config = None
        for record in manifest["records"]:
            if record.get("qa_status") != "VERIFIED" or not record.get("reviewed_by"):
                raise ValueError("Every public source-to-evidence mapping needs review")
            gold = load_artifact(path.parent, record["gold"])
            evidence = load_artifact(path.parent, record["evidence"])
            prediction = load_artifact(path.parent, record["prediction"])
            validator.validate(gold)
            if gold["synthetic"] is not False:
                raise ValueError("Public evaluation cannot relabel synthetic fixtures")
            if any(
                gold[k] != manifest[k]
                for k in ("dataset_family", "dataset_snapshot", "split")
            ):
                raise ValueError("Dataset provenance mismatch")
            if set(gold["fields"]) != set(HEADERS):
                raise ValueError("Expected canonical header keys")
            if (
                gold["receipt_id"] != evidence["receipt_id"]
                or gold["receipt_id"] in receipts
            ):
                raise ValueError("Wrong/duplicate receipt identity")
            receipts.add(gold["receipt_id"])
            validate_result(
                prediction, evidence, kie_run_id=UUID(prediction["kie_run_id"])
            )
            if config is not None and prediction["configuration"] != config:
                raise ValueError("Predictions use different configurations")
            config = prediction["configuration"]
            ids = {b.block_id for b in flatten(evidence)}
            allowed = set(HEADERS) | {"line_items." + k for k in LINE_FIELDS}
            mask = set(record.get("supported_fields", []))
            if not mask or not mask <= allowed:
                raise ValueError("Explicit supported-field mask required")
            all_cells = list(gold["fields"].values()) + [
                r[k] for r in gold["line_items"] for k in LINE_FIELDS
            ]
            for c in all_cells:
                if c["annotation_status"] == "PRESENT":
                    if (
                        c["normalized_value"] is None
                        or not c["source_block_ids"]
                        or not set(c["source_block_ids"]) <= ids
                    ):
                        raise ValueError(
                            "PRESENT public cell needs value and actual reviewed evidence"
                        )
                elif c["normalized_value"] is not None:
                    raise ValueError("Unavailable cell has a value")
            line_ids = [r["line_id"] for r in gold["line_items"]]
            if len(set(line_ids)) != len(line_ids):
                raise ValueError("Duplicate gold line IDs")
            prepared.append((gold, prediction, mask))
        headers = defaultdict(Counter)
        cells = defaultdict(Counter)
        totals = Counter()
        for gold, pred, mask in prepared:
            for field in HEADERS:
                g, p = gold["fields"][field], pred["fields"][field]
                if field not in mask or g["annotation_status"] != "PRESENT":
                    continue
                headers[field].update(
                    evaluated=1,
                    correct=int(
                        p["value_status"] == "PRESENT"
                        and p["normalized_value"] == g["normalized_value"]
                    ),
                )
            matches = row_matches(pred["line_items"], gold["line_items"])
            totals.update(
                gold_rows=len(gold["line_items"]),
                predicted_rows=len(pred["line_items"]),
                matched_rows=len(matches),
            )
            for i, j in matches:
                for field in LINE_FIELDS:
                    g, p = gold["line_items"][i][field], pred["line_items"][j][field]
                    if (
                        "line_items." + field not in mask
                        or g["annotation_status"] != "PRESENT"
                    ):
                        continue
                    cells[field].update(
                        evaluated=1,
                        correct=int(
                            p["value_status"] == "PRESENT"
                            and p["normalized_value"] == g["normalized_value"]
                        ),
                    )

        def rates(counters):
            return {
                k: dict(v, exact_match=v["correct"] / v["evaluated"])
                for k, v in counters.items()
            }

        report.update(
            status="COMPLETED",
            evaluated=len(prepared),
            configuration=config,
            metrics=dict(
                headers=rates(headers),
                line_items=dict(
                    totals,
                    cells=rates(cells),
                    detection_recall=totals["matched_rows"] / totals["gold_rows"]
                    if totals["gold_rows"]
                    else None,
                ),
                complete_canonical_invoice_accuracy=None,
            ),
            note="Only supported PRESENT cells scored; row cell metrics condition on matched rows. Not canonical-invoice accuracy.",
        )
        json.dumps(report, allow_nan=False)
    except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
        report.update(status="WAITING", metrics=None, evaluated=0, reasons=[str(exc)])
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("Use a new report path")
    report = evaluate(a.manifest)
    dump(a.output, report)
    return 0 if report["status"] == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
