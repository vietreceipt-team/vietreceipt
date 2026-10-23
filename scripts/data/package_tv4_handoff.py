"""Publish a self-contained pending-review handoff after independent integrity checks."""

import argparse
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from .common import dump, sha, write_text
from .verify_tv4_handoff import verify


def package(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(root):
        raise ValueError("Use a new archive outside the input directory")
    report = verify(root)
    if report["errors"]:
        raise ValueError("Handoff integrity failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "x", ZIP_DEFLATED) as archive:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                if not p.resolve().is_relative_to(root):
                    raise ValueError("Artifact symlink escapes handoff")
                archive.write(p, p.relative_to(root).as_posix())
        archive.writestr(
            "HANDOFF.txt",
            "TV2 development/validation handoff. Open index.html.\nQA and experiment protocol are PENDING owner review; no final test or oracle.\nSources/evidence are actual artifacts, not KIE-derived ground truth.\nHistorical request.json paths are provenance only; use the relative source/evidence refs in manifests.\n",
        )
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt archive")
    write_text(
        output.with_suffix(".zip.sha256"), sha(output) + "  " + output.name + "\n"
    )
    dump(
        output.with_suffix(".package.json"),
        dict(
            version="1.0.0-dev-candidate",
            archive_sha256=sha(output),
            bytes=output.stat().st_size,
            integrity=report,
            summary=json.loads((root / "summary.json").read_text()),
        ),
    )
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(package(a.root, a.output))


if __name__ == "__main__":
    main()
