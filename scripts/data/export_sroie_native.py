"""Convert authorized native SROIE task-3 folders into the preparation JSONL contract.

Requires explicit paths and snapshot evidence; does not accept terms, download
mirrors, infer licenses, or randomize the official train/test partition.
"""

import argparse
import json
from pathlib import Path
from .common import dump, sha, write_text


def export(root, images, labels, split, output, source, snapshot, terms):
    root = Path(root).resolve()
    images = Path(images).resolve()
    labels = Path(labels).resolve()
    output = Path(output)
    if output.exists():
        raise ValueError("Use a new export directory")
    if split not in ("train", "test"):
        raise ValueError("Preserve official native train/test")
    if not source or not snapshot or not terms:
        raise ValueError("Official source/archive/terms evidence required")
    if not images.is_relative_to(root) or not labels.is_relative_to(root):
        raise ValueError("Native folders must be under source root")
    files = {
        p.stem: p
        for p in images.iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    }
    records = []
    failures = []
    for label in sorted(labels.glob("*.txt")) + sorted(labels.glob("*.json")):
        try:
            native = json.loads(label.read_text(encoding="utf-8-sig"))
            if not isinstance(native, dict) or not {
                "company",
                "address",
                "date",
                "total",
            } <= set(native):
                raise ValueError("Not native SROIE task-3 JSON")
            image = files[label.stem]
            records.append(
                dict(
                    id=label.stem,
                    split=split,
                    image_path=image.relative_to(root).as_posix(),
                    annotation=native,
                )
            )
        except (ValueError, KeyError, OSError) as exc:
            failures.append(dict(label=label.name, reason=str(exc)))
    write_text(
        output / "export.jsonl",
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
    )
    dump(
        output / "intake.json",
        dict(
            source=source,
            snapshot=snapshot,
            terms_evidence=terms,
            native_split=split,
            exported=len(records),
            failures=failures,
            export_sha256=sha(output / "export.jsonl"),
            qa_status="SOURCE_REVIEW_PENDING",
        ),
    )
    return records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("root", "images", "labels", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    for key in ("split", "source", "snapshot", "terms"):
        p.add_argument("--" + key, required=True)
    a = p.parse_args()
    print(
        len(
            export(
                a.root,
                a.images,
                a.labels,
                a.split,
                a.output,
                a.source,
                a.snapshot,
                a.terms,
            )
        )
    )


if __name__ == "__main__":
    main()
