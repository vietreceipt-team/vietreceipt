"""Paired, reproducible development diagnostics using the existing metric kernel.

Never upgrades synthetic expectations to QA gold. Official metrics stay null;
the optional synthetic diagnostics are explicitly scoped software measurements.
"""

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.kie.v2.cells import select  # noqa: E402
from ai.kie.v2.config import BASELINE_GROUPING, HEADER_FIELDS  # noqa: E402
from ai.kie.v2.evaluation import MATCHING_VERSION, VERSION, metrics  # noqa: E402
from ai.table.structure import (  # noqa: E402
    STRATEGIES,
    STRUCTURE_STRATEGY,
    extract_table_structure,
)
from tests.kie_table_structure_fixtures import cases  # noqa: E402


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def table_metrics(pairs):
    measured = metrics(pairs)
    return {
        key: measured[key]
        for key in (
            "status_policy",
            "lines",
            "complete_table_accuracy",
        )
    }


def package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def compare(*, synthetic_diagnostics=False, repeats=5):
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    strategies = (BASELINE_GROUPING, STRUCTURE_STRATEGY)
    inputs = cases()
    pairs = {name: [] for name in strategies}
    times = {name: [] for name in strategies}
    failures = {name: [] for name in strategies}
    samples = []
    provenance = ROOT / "tests/fixtures/table_structure/provenance.json"
    # Validate persisted source hashes before any timing or scoring.
    manifest = json.loads(provenance.read_text(encoding="utf-8"))
    for record in manifest["records"]:
        for kind in ("image", "evidence", "expected"):
            artifact = record[kind]
            path = provenance.parent / artifact["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
                raise ValueError(f"Source hash mismatch: {path}")
        case = inputs[record["ruling"]]
        for kind, value in (("evidence", case["evidence"]), ("expected", case["gold"])):
            stored = json.loads(
                (provenance.parent / record[kind]["path"]).read_text(encoding="utf-8")
            )
            if stored != value:
                raise ValueError("Persisted ruling scene differs from runtime fixture")

    for index, (sample_id, case) in enumerate(inputs.items()):
        source = case["evidence"]
        page_count = len(source["pages"]) if "pages" in source else 1
        regions = [
            {"page_index": p, "bbox": [0, 0.18, 1, 0.60]} for p in range(page_count)
        ]
        sample = {
            "sample_id": sample_id,
            "base_document_id": case["base_document_id"],
            "template_id": case["template_id"],
            "split": case["split"],
            "evidence_sha256": digest(source),
            "expected_sha256": digest(case["gold"]),
            "layout_regions": regions,
            "variants": {},
        }
        for strategy in strategies[index % 2 :] + strategies[: index % 2]:
            durations = []
            prediction = None
            failure = None
            no_rows = 0
            review = 0
            for _ in range(repeats):
                start = perf_counter_ns()
                try:
                    tables = [
                        extract_table_structure(
                            source,
                            **region,
                            currency="VND",
                            strategy=strategy,
                        )
                        for region in regions
                    ]
                    lines = [row for table in tables for row in table["line_items"]]
                    for i, row in enumerate(lines, 1):
                        row["line_id"] = f"line-{i:04d}"
                    # Internal table-only metric input, not an invoice export.
                    prediction = {
                        "fields": {f: select(f, []) for f in HEADER_FIELDS},
                        "line_items": lines,
                        "consistency": {"checks": []},
                    }
                    no_rows = sum(
                        table["status"] == "NO_ROWS_DETECTED" for table in tables
                    )
                    review = sum(table["machine_needs_review"] for table in tables)
                except Exception as exc:
                    prediction = None
                    failure = f"{type(exc).__name__}: {exc}"
                durations.append((perf_counter_ns() - start) / 1_000_000)
            times[strategy].extend(durations)
            if failure:
                prediction = None
                failures[strategy].append(
                    {"sample_id": sample_id, "stage": "TABLE", "error": failure}
                )
            pairs[strategy].append((prediction, case["gold"]))
            sample["variants"][strategy] = {
                "duration_ms_median": statistics.median(durations),
                "failure": failure,
                "no_rows_regions": no_rows,
                "review_regions": review,
                "predicted_rows": len(prediction["line_items"]) if prediction else None,
                "prediction_sha256": digest(prediction),
                "synthetic_diagnostics": table_metrics([(prediction, case["gold"])])
                if synthetic_diagnostics
                else None,
            }
        samples.append(sample)
    implementation = [
        "ai/table/structure.py",
        "scripts/evaluate_table_structure.py",
        "scripts/generate_table_structure_sources.py",
        "tests/kie_table_structure_fixtures.py",
        "ai/kie/v2/evaluation.py",
        "ai/kie/v2/extraction.py",
        "ai/kie/v2/grouping.py",
        "ai/kie/v2/evidence.py",
        "ai/kie/v2/cells.py",
        "ai/kie/v2/normalization.py",
        "ai/kie/v2/config.py",
        "tests/kie_v2_fixtures.py",
    ]
    return {
        "status": "NOT_SCORED",
        "metrics": None,
        "reason": "No independently QA-reviewed Table development gold or signed comparison protocol; no final test inspected.",
        "scope": "synthetic table-only development software diagnostics; supplied Layout regions and evidence; no OCR/pixel ruling detection",
        "evaluator": VERSION,
        "matching_version": MATCHING_VERSION,
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {
            name: package_version(name)
            for name in (
                "jsonschema",
                "Pillow",
                "reportlab",
                "pypdfium2",
            )
        },
        "source_manifest_sha256": hashlib.sha256(provenance.read_bytes()).hexdigest(),
        "implementation_hash_encoding": "Git canonical source bytes; CRLF normalized to LF",
        "implementation_sha256": {
            p: hashlib.sha256(
                (ROOT / p).read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            for p in implementation
        },
        "sample_count": len(inputs),
        "base_document_count": len({c["base_document_id"] for c in inputs.values()}),
        "template_count": len({c["template_id"] for c in inputs.values()}),
        "split": "development",
        "synthetic": True,
        "timing_scope": "region API including evidence validation; excludes OCR/Layout/model time; sequential alternating strategy order, no warmup",
        "repeats_per_sample": repeats,
        "variants": {
            strategy: {
                "configuration": STRATEGIES[strategy],
                "currency": "VND (explicit synthetic scene)",
                "failure_count": len(failures[strategy]),
                "failures": failures[strategy],
                "duration_ms_median": statistics.median(times[strategy]),
                "no_rows_samples": sum(
                    s["variants"][strategy]["no_rows_regions"] > 0 for s in samples
                ),
                "synthetic_diagnostics": table_metrics(pairs[strategy])
                if synthetic_diagnostics
                else None,
            }
            for strategy in strategies
        },
        "samples": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--synthetic-diagnostics", action="store_true")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    report = compare(
        synthetic_diagnostics=args.synthetic_diagnostics, repeats=args.repeats
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
        print(
            f"NOT_SCORED; {report['sample_count']} synthetic development cases; {args.output}"
        )
    else:
        print(text, end="")
    return 2  # Missing QA/protocol never becomes an official scored benchmark.


if __name__ == "__main__":
    raise SystemExit(main())
