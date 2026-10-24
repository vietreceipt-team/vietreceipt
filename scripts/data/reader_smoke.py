"""Real TV3/TV4 execution on development files; never create reviewed/final gold."""

import argparse
import json
import mimetypes
import subprocess
import uuid
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from .common import dump, read_csv, resolve, sha


def run(root, out, all_routes=False):
    from ai.document_reader import DocumentReader, ReaderConfig
    from ai.kie.v2 import extract_invoice

    root, out = Path(root).resolve(), Path(out)
    if out.exists():
        raise ValueError("Use a new run directory")
    rows = read_csv(root / "rendered_manifest.csv")
    types = ("text_pdf", "image", "scanned_pdf") if all_routes else ("text_pdf",)
    reader = DocumentReader(config=ReaderConfig(orientation="none"))
    report = []
    packages = {}
    for package in (
        "paddleocr",
        "paddlepaddle",
        "paddlex",
        "pypdfium2",
        "Pillow",
        "reportlab",
    ):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    for source_type in types:
        row = next(
            r
            for r in rows
            if r["source_type"] == source_type
            and r["split"] == "train"
            and r["augmentation_type"] == "clean"
        )
        try:
            gold = json.loads(
                resolve(root, row["ground_truth_path"]).read_text(encoding="utf-8")
            )
            evidence, metadata = reader.process_with_metadata(
                str(resolve(root, row["document_path"])),
                content_type=mimetypes.guess_type(row["document_path"])[0],
                receipt_id=uuid.UUID(gold["receipt_id"]),
                ocr_run_id=uuid.uuid4(),
            )
            result = extract_invoice(evidence, kie_run_id=uuid.uuid4())
            dump(out / f"{source_type}.evidence.json", evidence)
            dump(out / f"{source_type}.kie.json", result)
            dump(out / f"{source_type}.metadata.json", metadata)
            report.append(
                dict(
                    route=source_type,
                    status="PASSED",
                    input=row["document_path"],
                    input_sha256=sha(resolve(root, row["document_path"])),
                    source_gold_sha256=sha(resolve(root, row["ground_truth_path"])),
                    page_sources=[p["source"] for p in metadata["pages"]],
                    kie_schema_valid=True,
                    accuracy=None,
                )
            )
        except Exception as exc:
            report.append(
                dict(
                    route=source_type,
                    status="FAILED",
                    error=f"{type(exc).__name__}: {exc}",
                    accuracy=None,
                )
            )
    dump(
        out / "report.json",
        dict(
            scope="development integration only",
            runs=report,
            source_gold_evidence_linked=False,
            final_evaluation=False,
            manifest_sha256=sha(root / "rendered_manifest.csv"),
            executed_at=datetime.now(timezone.utc).isoformat(),
            git_commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            git_dirty=bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain"], text=True
                ).strip()
            ),
            packages=packages,
        ),
    )
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--all-routes", action="store_true")
    a = p.parse_args()
    report = run(a.root, a.output, a.all_routes)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(r["status"] == "PASSED" for r in report) else 2


if __name__ == "__main__":
    raise SystemExit(main())
