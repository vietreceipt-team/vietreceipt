"""Package a validated synthetic development dataset for TV3 without public images."""

import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from .common import dump, sha, write_text
from .validate_ground_truth import audit


def package(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(root):
        raise ValueError("Use a new output path outside the dataset directory")
    report = audit(root / "rendered_manifest.csv", root)
    if report["status"] != "PASSED":
        raise ValueError("Dataset failed QA")
    # Do not accidentally distribute unrelated/public source data.
    from .common import read_csv

    if any(
        r.get("dataset_family") != "vietreceipt_synthetic"
        or r.get("synthetic") != "true"
        for r in read_csv(root / "manifest.csv")
    ):
        raise ValueError("This package command is for fictional synthetic data only")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "x", ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if not path.resolve().is_relative_to(root):
                raise ValueError("Symlink escapes dataset")
            archive.write(path, path.relative_to(root).as_posix())
        archive.writestr(
            "HANDOFF.txt",
            "VietReceipt Synthetic development dataset v0.2.0. NOT final verified gold.\n"
            "Unzip into a new directory. TV3 benchmark accepts tv3_train.json directly.\n"
            "Use references for OCR CER/WER; retain every failed input.\n"
            "Source gold has no OCR block linkage. Review links after actual reader execution.\n",
        )
    dump(output.with_suffix(".qa.json"), report)
    write_text(output.with_suffix(".sha256"), sha(output) + "  " + output.name + "\n")
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(package(a.root, a.output))


if __name__ == "__main__":
    main()
