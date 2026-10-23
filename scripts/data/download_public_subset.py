"""Download a pinned native HF shard and export a reproducible small development subset.

No test shards are downloaded by default. Downloads stay under ignored data/raw.
Requires huggingface_hub and pyarrow, see requirements-data-public.txt.
"""

import argparse
import io
import json
from pathlib import Path
from PIL import Image
from .common import dump, sha, write_text

REPOS = {
    "cord": "naver-clova-ix/cord-v2",
    "vietnamese_bill": "minhduc168/dataset-origin-vlm-extract-bill",
}


def download(family, out, limit=10, revision=None, max_mb=600):
    from huggingface_hub import HfApi, hf_hub_download
    import pyarrow.parquet as pq

    out = Path(out).resolve()
    if out.exists():
        raise ValueError("Use a new snapshot directory")
    if limit < 1:
        raise ValueError("limit must be positive")
    repo = REPOS[family]
    info = HfApi().dataset_info(repo, revision=revision, files_metadata=True)
    revision = info.sha
    shards = sorted(
        (
            s
            for s in info.siblings
            if s.rfilename.startswith("data/train-")
            and s.rfilename.endswith(".parquet")
        ),
        key=lambda s: s.rfilename,
    )
    if not shards:
        raise ValueError("No native train Parquet shard; inspect source format")
    shard = shards[0]
    if shard.size is None or shard.size > max_mb * 1024 * 1024:
        raise ValueError("Shard exceeds explicit download budget")
    path = Path(
        hf_hub_download(
            repo_id=repo,
            repo_type="dataset",
            revision=revision,
            filename=shard.rfilename,
            local_dir=str(out / "snapshot"),
        )
    )
    card = Path(
        hf_hub_download(
            repo_id=repo,
            repo_type="dataset",
            revision=revision,
            filename="README.md",
            local_dir=str(out / "snapshot"),
        )
    )
    records = []
    for batch in pq.ParquetFile(path).iter_batches(batch_size=min(limit, 32)):
        for native in batch.to_pylist():
            image = native["image"]
            data = image.get("bytes")
            if not data:
                raise ValueError(
                    "Embedded native image bytes required; no image-path guessing"
                )
            original = native.get("source_image")
            annotation = (
                {"master_data": native["master_data"]}
                if family == "vietnamese_bill"
                else json.loads(native["ground_truth"])
            )
            if original is None:
                original = annotation.get("meta", {}).get("image_id")
            if original is None:
                raise ValueError(
                    "Native sample ID unavailable; do not invent upstream IDs"
                )
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
            local = "images/" + str(len(records)) + ".png"
            # Preserve exact native bytes, choose actual file extension by signature.
            with Image.open(io.BytesIO(data)) as im:
                ext = im.format.lower()
            local = (
                "images/" + str(len(records)) + (".jpg" if ext == "jpeg" else "." + ext)
            )
            (out / "images").mkdir(parents=True, exist_ok=True)
            (out / local).write_bytes(data)
            records.append(
                dict(
                    id=str(original),
                    split="train",
                    image_path=local,
                    annotation=annotation,
                )
            )
            if len(records) >= limit:
                break
        if len(records) >= limit:
            break
    export = out / "export.jsonl"
    write_text(
        export, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    )
    dump(
        out / "snapshot.json",
        dict(
            repo=repo,
            revision=revision,
            source=f"https://huggingface.co/datasets/{repo}/tree/{revision}",
            native_shard=shard.rfilename,
            shard_sha256=sha(path),
            card_sha256=sha(card),
            export_sha256=sha(export),
            subset_size=len(records),
            selection="first N records of first native train shard",
            split="train",
            final_eligible=False,
            scope="development subset; not full dataset",
        ),
    )
    return records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--family", choices=REPOS, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--revision")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--max-mb", type=int, default=600)
    a = p.parse_args()
    print(
        f"Downloaded {len(download(a.family, a.out, a.limit, a.revision, a.max_mb))} native samples"
    )


if __name__ == "__main__":
    main()
