"""Audit/export every row of an already pinned native train shard, without a new download."""

import argparse
import io
import json
from pathlib import Path
from PIL import Image
from .common import dump, resolve, sha


def export(cached, out, family):
    import pyarrow.parquet as pq

    cached, out = Path(cached).resolve(), Path(out).resolve()
    if out.exists():
        raise ValueError("New export directory required")
    metadata = json.loads((cached / "snapshot.json").read_text())
    shard = resolve(cached / "snapshot", metadata["native_shard"])
    if sha(shard) != metadata["shard_sha256"]:
        raise ValueError("Pinned shard checksum mismatch")
    out.mkdir(parents=True)
    (out / "images").mkdir()
    count = 0
    failures = []
    with (out / "export.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for batch in pq.ParquetFile(shard).iter_batches(batch_size=16):
            for index, native in enumerate(batch.to_pylist()):
                try:
                    data = native["image"]["bytes"]
                    with Image.open(io.BytesIO(data)) as image:
                        extension = (
                            ".jpg"
                            if image.format == "JPEG"
                            else "." + image.format.lower()
                        )
                        image.verify()
                    annotation = (
                        {"master_data": native["master_data"]}
                        if family == "vietnamese_bill"
                        else {
                            k: native[k]
                            for k in ("entities", "words", "bboxes", "image_size")
                        }
                        if family == "sroie_curated"
                        else json.loads(native["ground_truth"])
                    )
                    original = native.get("source_image", native.get("key"))
                    if original is None:
                        original = annotation.get("meta", {}).get("image_id")
                    if original is None:
                        raise ValueError("Native sample identity missing")
                    if annotation.get("meta", {}).get("split", "train") != "train":
                        raise ValueError("Non-train row in pinned train shard")
                    relative = f"images/{count}{extension}"
                    (out / relative).write_bytes(data)
                    stream.write(
                        json.dumps(
                            dict(
                                id=str(original),
                                split="train",
                                image_path=relative,
                                annotation=annotation,
                            ),
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    count += 1
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    failures.append(dict(row=count + len(failures), reason=str(exc)))
    dump(
        out / "audit.json",
        dict(
            family=family,
            revision=metadata["revision"],
            shard_sha256=sha(shard),
            native_rows=pq.ParquetFile(shard).metadata.num_rows,
            exported=count,
            broken_records=failures,
            export_sha256=sha(out / "export.jsonl"),
            selection="all rows of pinned first native train shard",
            final_test_included=False,
            annotation_review="NOT_INDEPENDENTLY_REVIEWED",
        ),
    )
    return count


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cached", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--family", choices=("cord", "vietnamese_bill", "sroie_curated"), required=True
    )
    a = p.parse_args()
    print(export(a.cached, a.out, a.family))


if __name__ == "__main__":
    main()
