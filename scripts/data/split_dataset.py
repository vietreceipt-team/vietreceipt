"""Explicit template partition, before augmentation; preserve official public splits."""

import argparse
import json
from pathlib import Path
from .common import read_csv, write_csv


def split(rows, partition):
    if any(r.get("parent_sample_id") for r in rows):
        raise ValueError("Split before augmentation")
    if any(r.get("official_split") for r in rows):
        raise ValueError("Preserve official splits")
    if set(partition.values()) - {"train", "validation", "test"}:
        raise ValueError("Invalid split assignment")
    return [dict(r, split=partition[r["layout_id"]]) for r in rows]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--partition", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("Refusing to overwrite manifest")
    write_csv(
        a.output, split(read_csv(a.manifest), json.loads(a.partition.read_text()))
    )


if __name__ == "__main__":
    main()
