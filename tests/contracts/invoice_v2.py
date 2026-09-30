"""Shared V2 contract cases using explicitly synthetic public examples."""

import copy
import json
from pathlib import Path
from uuid import UUID

from jsonschema import ValidationError

from ai.kie.v2 import extract_invoice
from ai.kie.v2.contract import validate_result


def run():
    root = Path(__file__).resolve().parents[2]
    evidence = json.loads(
        (root / "examples/invoice-v2-synthetic-evidence.json").read_text()
    )
    result = json.loads(
        (root / "examples/invoice-v2-synthetic-result.json").read_text()
    )
    run_id = UUID(result["kie_run_id"])
    validate_result(result, evidence, kie_run_id=run_id)
    assert extract_invoice(evidence, kie_run_id=run_id) == result
    cases = []
    for key in (
        "predicted_value",
        "normalization",
        "confidence",
        "heuristic_score",
        "score_version",
        "machine_needs_review",
        "review_reasons",
        "review_policy_version",
        "source_block_ids",
    ):
        bad = copy.deepcopy(result)
        del bad["fields"]["invoice_number"][key]
        cases.append(bad)
    for key in (
        "extractor",
        "configuration",
        "source_ocr_run_id",
        "kie_run_id",
        "receipt_id",
    ):
        bad = copy.deepcopy(result)
        del bad[key]
        cases.append(bad)
    for key in (
        "machine_needs_review",
        "review_reasons",
        "review_policy_version",
        "source_block_ids",
    ):
        bad = copy.deepcopy(result)
        del bad["line_items"][0][key]
        cases.append(bad)
    for status in ("NOT_PRESENT", "AMBIGUOUS", "UNREADABLE", "UNKNOWN"):
        bad = copy.deepcopy(result)
        bad["fields"]["invoice_number"]["value_status"] = status
        cases.append(bad)
    for ids in ([], ["outside"], ["p0_b2", "p0_b2"]):
        bad = copy.deepcopy(result)
        bad["fields"]["invoice_number"]["source_block_ids"] = ids
        cases.append(bad)
    for bad in cases:
        try:
            validate_result(bad, evidence, kie_run_id=run_id)
        except (ValueError, ValidationError):
            continue
        raise AssertionError("Invalid V2 mutation accepted")
    print(
        f"PASS: Invoice V2: 2 positive cases, {len(cases)} negative cases rejected (synthetic)"
    )
