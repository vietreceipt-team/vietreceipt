"""Create a PENDING source-scoring plan from TV2 bytes; never approves any labels."""

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from ai.document_reader import ReaderConfig
from ai.kie.v2.config import CONFIGURATION
from ai.kie.v2.evaluation import VERSION
from ai.kie.v2.source_evaluation import SOURCE_MATCHING_VERSION
from scripts.backend_evaluation_reports import write_json
from scripts.evaluate_source_backend_v2 import PROFILE, SCHEMA, geometry
from scripts.prepare_tv2_backend_manifest import prepare


def build(root, output, revision):
    root = root.resolve()
    output.mkdir(parents=True, exist_ok=False)
    capture = prepare(root, output / "sources", revision)
    split_data = {
        s: json.loads((root / f"{s}-manifest.json").read_text())
        for s in ("train", "validation")
    }
    registry = [
        dict(
            id=r["record_id"],
            base_document_id=r["base_document_id"],
            template_id=r["template_id"],
            source_sha256=r["source"]["sha256"],
            split=s,
        )
        for s, m in split_data.items()
        for r in m["records"]
    ]
    sources = {r["id"]: r for r in capture["samples"]}
    records = []
    reader = asdict(ReaderConfig())
    for record in split_data["validation"]["records"]:
        sid = record["record_id"]
        source = output / "sources" / sources[sid]["path"]
        mime = (
            "application/pdf"
            if source.suffix == ".pdf"
            else "image/jpeg"
            if source.suffix in (".jpeg", ".jpg")
            else "image/png"
        )
        refs = {}
        for key, ref_key in (
            ("gold", "source_gold"),
            ("regions", "source_row_regions"),
        ):
            ref = record[ref_key]
            path = (root / ref["path"]).resolve()
            if (
                not path.is_relative_to(root)
                or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]
            ):
                raise ValueError("Source annotation path/hash mismatch")
            target = output / f"{sid}-{key}.json"
            shutil.copyfile(path, target)
            refs[key] = dict(path=target.name, sha256=ref["sha256"])
        gold = json.loads((output / refs["gold"]["path"]).read_text())
        records.append(
            dict(
                id=sid,
                source_sample_id=gold["sample_id"],
                source_receipt_id=gold["receipt_id"],
                base_document_id=record["base_document_id"],
                template_id=record["template_id"],
                source=dict(
                    path="sources/" + source.name,
                    sha256=record["source"]["sha256"],
                    content_type=mime,
                ),
                **refs,
                geometry=dict(
                    profile=PROFILE,
                    page_sizes=geometry(source.read_bytes(), mime, reader["dpi"]),
                ),
                qa=dict(
                    status="PENDING_REVIEW",
                    annotated_by="TV2 synthetic generator; reviewer must confirm attribution",
                    reviewed_by=None,
                    reviewed_at=None,
                    source_sha256=record["source"]["sha256"],
                    gold_sha256=refs["gold"]["sha256"],
                    regions_sha256=refs["regions"]["sha256"],
                ),
            )
        )
    plan = dict(
        schema_version=SCHEMA,
        dataset_family=capture["dataset"],
        dataset_snapshot=capture["version"],
        split="validation",
        synthetic=True,
        authorized=True,
        sample_count=len(records),
        frozen=True,
        freeze_scope="development membership/hash only; not final approval",
        frozen_at=None,
        qa_status="PENDING_REVIEW",
        source_revision=revision,
        protocol=dict(
            evaluator_version=VERSION,
            matching_version=SOURCE_MATCHING_VERSION,
            coordinate_profile=PROFILE,
            scope="13_headers+line_items_tax_excluded",
            configuration=CONFIGURATION,
            reader_configuration=reader,
            worker_source_sha256=None,
            approved_at=None,
            approved_by={role: None for role in ("TV1", "TV2", "TV4", "TV5")},
        ),
        records=records,
        split_registry=registry,
    )
    write_json(output / "plan.pending.json", plan)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    plan = build(args.root, args.output, args.source_revision)
    print(
        f"Prepared {plan['sample_count']} pending source records; no approvals or accuracy granted"
    )


if __name__ == "__main__":
    main()
