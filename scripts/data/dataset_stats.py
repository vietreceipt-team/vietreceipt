"""Count actual files and independent base documents separately."""

import argparse
import json
from collections import Counter
from pathlib import Path
from .common import dump, read_csv, resolve


def stats(manifest, root):
    rows = read_csv(manifest)
    result = {
        "file_count": len(rows),
        "base_document_count": len({r["sample_id"] for r in rows}),
    }
    for key in (
        "dataset_family",
        "dataset_version",
        "split",
        "layout_id",
        "source_type",
        "augmentation_type",
    ):
        result[key] = dict(Counter(r.get(key, "unknown") for r in rows))
    gold = {
        r["sample_id"]: json.loads(
            resolve(root, r["ground_truth_path"]).read_text(encoding="utf-8")
        )
        for r in rows
    }
    result["line_counts"] = dict(
        Counter(str(len(g["line_items"])) for g in gold.values())
    )
    result["header_present"] = {
        k: sum(g["fields"][k]["annotation_status"] == "PRESENT" for g in gold.values())
        for k in next(iter(gold.values()))["fields"]
    }
    result["final_evaluation"] = False
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    dump(a.output, stats(a.manifest, a.root))


if __name__ == "__main__":
    main()
