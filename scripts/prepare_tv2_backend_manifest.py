"""Import all TV2 development validation sources for HTTP workflow capture, not accuracy."""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root, output, source_revision):
    root = root.resolve()
    manifests = {}
    seen = set()
    partitions = {key: {} for key in ("base_document_id", "template_id", "sha256")}
    sources = []
    for split in ("train", "validation"):
        path = root / f"{split}-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if (
            manifest["schema_version"] != "tv2-tv4-handoff-candidate-0.1"
            or manifest["split"] != split
            or manifest["synthetic"] is not True
            or manifest["frozen"] is not True
            or not manifest.get("qa_status")
            or not manifest.get("freeze_scope")
            or manifest["sample_count"] != len(manifest["records"])
            or not manifest["records"]
        ):
            raise ValueError("Invalid development handoff split/count/freeze")
        manifests[split] = manifest
        for record in manifest["records"]:
            sid = record["record_id"]
            source = record["source"]
            if (
                not isinstance(sid, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", sid)
                or sid in seen
                or record["split"] != split
                or record.get("final_eligible") not in (False, "false")
                or not record.get("qa_status")
            ):
                raise ValueError("Duplicate, unsafe, final or wrong-split record")
            seen.add(sid)
            for key in partitions:
                value = source[key] if key == "sha256" else record[key]
                if not value or not isinstance(value, str):
                    raise ValueError("Missing parent/template/source identity")
                partitions[key].setdefault(value, set()).add(split)
            path = (root / source["path"]).resolve()
            if (
                not path.is_relative_to(root)
                or path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".pdf")
                or sha(path) != source["sha256"]
            ):
                raise ValueError("Unsafe, unsupported or changed original input")
            if split == "validation":
                sources.append((record, path))
    if any(
        len(splits) > 1 for values in partitions.values() for splits in values.values()
    ):
        raise ValueError("Source/base/template crosses train and validation")
    validation = manifests["validation"]
    if any(
        manifests["train"][key] != validation[key]
        for key in ("dataset_family", "dataset_snapshot", "synthetic")
    ):
        raise ValueError("Dataset identity differs across splits")
    output.mkdir(parents=True, exist_ok=False)
    samples = []
    for record, path in sources:
        name = record["record_id"] + path.suffix.lower()
        shutil.copyfile(path, output / name)
        samples.append(
            dict(
                id=record["record_id"],
                path=name,
                sha256=record["source"]["sha256"],
                condition=record["source_type"],
                base_document_id=record["base_document_id"],
                template_id=record["template_id"],
                augmentation_type=record["augmentation_type"],
                qa_status=record["qa_status"],
            )
        )
    result = dict(
        dataset=validation["dataset_family"],
        version=validation["dataset_snapshot"],
        split="validation",
        synthetic=True,
        qa_status=validation["qa_status"],
        purpose="development_workflow_capture_only",
        accuracy_eligible=False,
        provenance=dict(
            declared_source_revision=source_revision,
            train_manifest_sha256=sha(root / "train-manifest.json"),
            validation_manifest_sha256=sha(root / "validation-manifest.json"),
            freeze_scope=validation["freeze_scope"],
            base_documents=len({s["base_document_id"] for s in samples}),
            final_test_included=False,
            selection="All validation sources, without filtering on prior reader success",
        ),
        samples=samples,
    )
    (output / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    result = prepare(args.root, args.output, args.source_revision)
    print(
        f"Prepared {len(result['samples'])} validation sources; accuracy_eligible=false"
    )


if __name__ == "__main__":
    main()
