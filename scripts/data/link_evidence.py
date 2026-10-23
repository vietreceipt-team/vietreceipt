"""Apply an explicitly reviewed cell-to-block mapping to a copy of source gold."""

import argparse
import copy
import json
from pathlib import Path
from .common import HEADERS, ROOT, dump, sha


def link(gold, evidence, review):
    from ai.kie.v2.evidence import flatten
    from ai.kie.v2.evaluation import validate_gold

    if (
        review.get("approved") is not True
        or not review.get("reviewed_by")
        or not review.get("reviewed_at")
    ):
        raise ValueError("An explicit human-reviewed mapping is required")
    ids = {b.block_id for b in flatten(evidence)}
    output = copy.deepcopy(gold)
    if output["receipt_id"] != evidence["receipt_id"]:
        raise ValueError("Receipt identity mismatch")
    pairs = [("fields." + k, c) for k, c in output["fields"].items()]
    pairs += [
        (f"line_items.{n}.{k}", row[k])
        for n, row in enumerate(output["line_items"])
        for k in ("description", "unit", "quantity", "unit_price", "amount")
    ]
    expected = {key for key, c in pairs if c["annotation_status"] == "PRESENT"}
    if set(review.get("links", {})) != expected:
        raise ValueError("Mapping must cover exactly the PRESENT cells")
    for key, c in pairs:
        if key in expected:
            blocks = review["links"][key]
            if (
                not isinstance(blocks, list)
                or not blocks
                or len(set(blocks)) != len(blocks)
                or not set(blocks) <= ids
            ):
                raise ValueError("Unknown, empty or duplicate block IDs: " + key)
            c["source_block_ids"] = blocks
    if output["synthetic"]:
        validate_gold(output, evidence, output)
    else:
        # Sparse native public gold need not state a currency. Do not apply
        # the strict full-invoice currency defaults to a native-task annotation.
        from jsonschema import Draft202012Validator, FormatChecker

        schema = json.loads(
            (ROOT / "schemas/invoice-annotation.v2.schema.json").read_text()
        )
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(output)
        if set(output["fields"]) != set(HEADERS):
            raise ValueError(
                "Expected all canonical keys, with UNKNOWN for unsupported fields"
            )
        if len({r["line_id"] for r in output["line_items"]}) != len(
            output["line_items"]
        ):
            raise ValueError("Duplicate row IDs")
        for key, c in pairs:
            if (c["annotation_status"] == "PRESENT") != (
                c["normalized_value"] is not None
            ):
                raise ValueError("Cell status/value mismatch: " + key)
        json.dumps(output, allow_nan=False)
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("gold", "evidence", "review", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("Never overwrite original gold")
    review = json.loads(a.review.read_text(encoding="utf-8"))
    if review.get("gold_sha256") != sha(a.gold) or review.get("evidence_sha256") != sha(
        a.evidence
    ):
        raise ValueError("Review does not refer to these exact source files")
    output = link(
        json.loads(a.gold.read_text(encoding="utf-8")),
        json.loads(a.evidence.read_text(encoding="utf-8")),
        review,
    )
    dump(a.output, output)
    dump(
        a.output.with_suffix(".review.json"),
        dict(review=review, linked_gold_sha256=sha(a.output)),
    )


if __name__ == "__main__":
    main()
