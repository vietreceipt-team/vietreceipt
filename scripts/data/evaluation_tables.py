"""Export traceable tables from completed, dataset-specific TV4 evaluator reports.

Does not create predictions, gold or replacement metrics. Incomplete evaluation
is reported as WAITING with null metrics; no guessed results enter the tables.
"""

import argparse
import json
from pathlib import Path
from .common import dump, sha, write_csv


def tables(paths, output):
    output = Path(output)
    if output.exists():
        raise ValueError("Use a new output directory")
    rows = []
    waiting = []
    for path in paths:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        if report.get("status") != "COMPLETED" or not report.get("metrics"):
            waiting.append(
                dict(
                    report=str(path),
                    reasons=report.get("reasons", ["Evaluation incomplete"]),
                )
            )
            continue
        required = (
            "dataset_family",
            "dataset_snapshot",
            "split",
            "template_regime",
            "manifest_sha256",
            "git_commit",
            "configuration",
            "evaluator_version",
        )
        if any(not report.get(k) for k in required) or report.get("evaluated", 0) <= 0:
            raise ValueError("Completed report lacks dataset/configuration provenance")
        metrics = report["metrics"]
        prefix = dict(
            dataset_family=report["dataset_family"],
            dataset_version=report["dataset_snapshot"],
            split=report["split"],
            template_regime=report["template_regime"],
            samples=report["evaluated"],
            git_commit=report["git_commit"],
            manifest_sha256=report["manifest_sha256"],
            configuration=json.dumps(report["configuration"], sort_keys=True),
            result_scope=report.get("result_scope", "unspecified"),
            condition=report.get("condition", "unspecified"),
            source_route=report.get("source_route", "unspecified"),
            report_sha256=sha(path),
        )

        def append_values(section, values):
            for name, value in values.items():
                if isinstance(value, dict):
                    append_values(section + "." + name, value)
                elif type(value) in (int, float) or value is None:
                    rows.append(dict(prefix, section=section, metric=name, value=value))

        for field, values in metrics.get("headers", {}).items():
            append_values("header." + field, values)
        for key, value in metrics.items():
            if key != "headers":
                if isinstance(value, dict):
                    append_values(key, value)
                elif type(value) in (int, float) or value is None:
                    append_values("invoice", {key: value})
    # Never pool scores across dataset families, conditions or template regimes.
    if rows:
        write_csv(output / "evaluation_tables.csv", rows)
    dump(
        output / "status.json",
        dict(
            status="COMPLETED" if rows and not waiting else "WAITING",
            metric_rows=len(rows),
            incomplete=waiting,
            pooled_accuracy=None,
            note="Run separate verified manifests for each dataset and robustness slice; preserve all raw reports.",
        ),
    )
    return rows, waiting


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reports", type=Path, nargs="+", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    rows, waiting = tables(a.reports, a.output)
    return 0 if rows and not waiting else 2


if __name__ == "__main__":
    raise SystemExit(main())
