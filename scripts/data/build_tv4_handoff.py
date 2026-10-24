"""Capture all declared development inputs, actual reader evidence and alignment candidates.

Never uses KIE predictions as gold. Review gates remain pending until actual
owner review; failures and missing OCR content remain part of the inventory.
"""

import argparse
import copy
import json
import platform
import re
import subprocess
import sys
import unicodedata
import uuid
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .common import dump, read_csv, resolve, sha, write_csv
from .generate_synthetic import font_path


def compact(text):
    return "".join(unicodedata.normalize("NFC", str(text)).casefold().split())


def source_regions(spec, font):
    output = []
    for e in spec["entries"]:
        if not e["key"].startswith(("fields.", "line_items.")):
            continue
        width = pdfmetrics.stringWidth(e["text"], font, e["size"])
        x0, x1 = e["x"] / spec["width"], (e["x"] + width) / spec["width"]
        y0, y1 = (
            (e["y"] - e["size"] * 1.1) / spec["height"],
            (e["y"] + e["size"] * 0.3) / spec["height"],
        )
        output.append(
            dict(
                cell=e["key"],
                page_index=0,
                text=e["text"],
                selected_value_text=e["text"].split(": ", 1)[1]
                if e["key"].startswith("fields.")
                else e["text"],
                bounds=[x0, y0, x1, y1],
                coordinate_system="normalized top-left source page",
                annotation_origin="generator render specification, not OCR/KIE",
                qa_status="AUTOMATED_SOURCE_CHECK_ONLY",
            )
        )
    return output


def align(source_gold, regions, evidence):
    gold = copy.deepcopy(source_gold)
    gold["receipt_id"] = evidence["receipt_id"]
    blocks = [b for p in evidence["pages"] for b in p["evidence"]["blocks"]]
    rows = []
    for region in regions:
        x0, y0, x1, y1 = region["bounds"]
        candidates = []
        for b in blocks:
            xs = [p["x"] for p in b["polygon"]]
            ys = [p["y"] for p in b["polygon"]]
            bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
            overlap = max(0, min(x1, bx1) - max(x0, bx0)) * max(
                0, min(y1, by1) - max(y0, by0)
            )
            area = max(1e-12, min((x1 - x0) * (y1 - y0), (bx1 - bx0) * (by1 - by0)))
            if overlap / area >= 0.4:
                candidates.append(b)
        candidates.sort(key=lambda b: b["reading_order"])
        expected = compact(region["selected_value_text"])
        observed = " ".join(b["text"] for b in candidates)
        if re.fullmatch(r"[\d.,]+", expected):
            matched = re.sub(r"\D", "", observed) == re.sub(r"\D", "", expected)
        else:
            matched = expected in compact(observed)
        ids = [b["block_id"] for b in candidates]
        parts = region["cell"].split(".")
        target = (
            gold["fields"][parts[1]]
            if parts[0] == "fields"
            else gold["line_items"][int(parts[1])][parts[2]]
        )
        target["source_block_ids"] = ids
        rows.append(
            dict(
                cell=region["cell"],
                source_text=region["selected_value_text"],
                observed_text=observed,
                source_block_ids=ids,
                candidate_block_ids=[b["block_id"] for b in candidates],
                text_agrees=bool(matched and candidates),
                status=(
                    "CANDIDATE_REQUIRES_REVIEW"
                    if matched
                    else "SPATIAL_CANDIDATE_REQUIRES_REVIEW"
                )
                if ids
                else "UNALIGNED",
                reason=(
                    ""
                    if matched
                    else "Real spatial block exists but OCR text differs; source gold retained"
                )
                if ids
                else "No actual OCR block overlaps the source region",
            )
        )
    usage = Counter(i for r in rows for i in r["source_block_ids"])
    for r in rows:
        if any(usage[i] > 1 for i in r["source_block_ids"]):
            r["status"] = "SHARED_BLOCK_REQUIRES_REVIEW"
    return gold, rows


def worker(request, output):
    from ai.document_reader import DocumentReader, ReaderConfig

    req = json.loads(Path(request).read_text(encoding="utf-8"))
    evidence, metadata = DocumentReader(
        config=ReaderConfig(orientation="none")
    ).process_with_metadata(
        Path(req["source"]).read_bytes(),
        content_type=req["content_type"],
        receipt_id=uuid.UUID(req["receipt_id"]),
        ocr_run_id=uuid.UUID(req["ocr_run_id"]),
    )
    dump(output, dict(evidence=evidence, metadata=metadata))


def build(root, out, timeout=180, base_limit=None):
    import shutil

    root, out = Path(root).resolve(), Path(out).resolve()
    if out.exists():
        raise ValueError("Use a new handoff directory")
    rows = read_csv(root / "rendered_manifest.csv")
    bases = sorted({r["sample_id"] for r in rows})
    if base_limit is not None:
        bases = bases[:base_limit]
    selected = [
        r
        for r in rows
        if r["sample_id"] in bases
        and r["split"] in ("train", "validation")
        and (
            (
                r["augmentation_type"] == "clean"
                and r["source_type"] in ("text_pdf", "image", "scanned_pdf")
            )
            or (r["augmentation_type"] == "blur" and r["source_type"] == "image")
        )
    ]
    if not selected:
        raise ValueError("No eligible development inputs")
    generation = json.loads((root / "generation.json").read_text())
    fp = font_path()
    if sha(fp) != generation["font_sha256"]:
        raise ValueError("Source font hash mismatch")
    pdfmetrics.registerFont(TTFont("TV4Source", str(fp)))
    out.mkdir(parents=True)
    write_csv(out / "selection.csv", selected)
    dump(
        out / "selection-freeze.json",
        dict(
            purpose="development validation membership freeze, not final test",
            selection_sha256=sha(out / "selection.csv"),
            created_at=datetime.now(timezone.utc).isoformat(),
            policy="all train/validation bases, clean three routes + blur PNG; never select by OCR success",
            base_limit=base_limit,
            record_count=len(selected),
            final_test_included=False,
        ),
    )
    records = []
    failures = []
    for row in selected:
        sid = row["variant_id"]
        folder = out / "records" / sid
        folder.mkdir(parents=True)
        source = resolve(root, row["document_path"])
        gold_path = resolve(root, row["ground_truth_path"])
        if (
            sha(source) != row["document_sha256"]
            or sha(gold_path) != row["ground_truth_sha256"]
        ):
            raise ValueError("Source hash mismatch before reader: " + sid)
        local_source = folder / ("source" + source.suffix)
        shutil.copyfile(source, local_source)
        shutil.copyfile(gold_path, folder / "source-gold.json")
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        spec = json.loads(
            resolve(root, row["render_spec_path"]).read_text(encoding="utf-8")
        )
        regions = source_regions(spec, "TV4Source")
        dump(folder / "source-regions.json", regions)
        receipt = uuid.uuid5(uuid.UUID(gold["receipt_id"]), sid)
        run = uuid.uuid4()
        request = dict(
            source=str(local_source),
            content_type="application/pdf" if source.suffix == ".pdf" else "image/png",
            receipt_id=str(receipt),
            ocr_run_id=str(run),
        )
        dump(folder / "request.json", request)
        record = dict(
            row,
            record_id=sid,
            source_receipt_id=gold["receipt_id"],
            receipt_id=str(receipt),
            reader_run_id=str(run),
            qa_status="PENDING_REVIEW",
            mapping_version="source-spatial-candidate-0.1",
            license="team-generated fictional synthetic",
            reader_status="FAILED",
            alignment_status="READER_FAILED",
        )
        with (folder / "reader.log").open("w", encoding="utf-8") as log:
            try:
                process = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.data.build_tv4_handoff",
                        "--worker",
                        str(folder / "request.json"),
                        "--worker-output",
                        str(folder / "reader-output.json"),
                    ],
                    stdout=log,
                    stderr=log,
                    timeout=timeout,
                )
                if process.returncode != 0:
                    raise RuntimeError("Reader worker exit " + str(process.returncode))
                result = json.loads(
                    (folder / "reader-output.json").read_text(encoding="utf-8")
                )
                from ai.document_reader.contract import validate_document

                validate_document(result["evidence"])
                dump(folder / "evidence.json", result["evidence"])
                dump(folder / "reader-metadata.json", result["metadata"])
                aligned, alignment = align(gold, regions, result["evidence"])
                dump(folder / "aligned-gold-candidate.json", aligned)
                dump(folder / "alignment.json", alignment)
                counts = Counter(r["status"] for r in alignment)
                record.update(
                    reader_status="SUCCESS",
                    alignment_status="COMPLETE_CANDIDATE"
                    if not counts["UNALIGNED"]
                    and not counts["SHARED_BLOCK_REQUIRES_REVIEW"]
                    else "PARTIAL_CANDIDATE",
                    alignment_counts=dict(counts),
                    route=[p["source"] for p in result["metadata"]["pages"]],
                    evidence_sha256=sha(folder / "evidence.json"),
                    aligned_gold_sha256=sha(folder / "aligned-gold-candidate.json"),
                )
                for cell in alignment:
                    if cell["status"] != "CANDIDATE_REQUIRES_REVIEW":
                        failures.append(
                            dict(
                                record_id=sid,
                                stage="alignment",
                                cell=cell["cell"],
                                reason=cell["reason"] or cell["status"],
                            )
                        )
            except (Exception, subprocess.TimeoutExpired) as exc:
                record["reader_error"] = f"{type(exc).__name__}: {exc}"
                failures.append(
                    dict(
                        record_id=sid,
                        stage="reader",
                        cell="",
                        reason=record["reader_error"],
                    )
                )
        for key, name in [
            ("source", "source" + source.suffix),
            ("source_gold", "source-gold.json"),
            ("source_regions", "source-regions.json"),
        ]:
            record[key] = {
                "path": (folder / name).relative_to(out).as_posix(),
                "sha256": sha(folder / name),
            }
        if record["reader_status"] == "SUCCESS":
            for key, name in [
                ("evidence", "evidence.json"),
                ("gold", "aligned-gold-candidate.json"),
            ]:
                record[key] = {
                    "path": (folder / name).relative_to(out).as_posix(),
                    "sha256": sha(folder / name),
                }
        records.append(record)
        dump(folder / "record.json", record)
        print(
            f"{len(records)}/{len(selected)} {sid}: {record['reader_status']} / {record['alignment_status']}",
            flush=True,
        )
    for split in ("train", "validation"):
        subset = [r for r in records if r["split"] == split]
        dump(
            out / f"{split}-manifest.json",
            dict(
                schema_version="tv2-tv4-handoff-candidate-0.1",
                dataset_family="vietreceipt_synthetic",
                dataset_snapshot=generation["generator_version"],
                split=split,
                synthetic=True,
                sample_count=len(subset),
                base_sample_count=len({r["sample_id"] for r in subset}),
                frozen=True,
                freeze_scope="development sample membership and artifact hashes only",
                qa_status="PENDING_REVIEW",
                experiment={
                    "status": "PENDING_TV1_TV4_PROTOCOL",
                    "baseline": "geometry_grouping_v2",
                    "variant": "relation_grouping_v2_1",
                },
                oracle_delivered=False,
                records=subset,
            ),
        )
    if failures:
        write_csv(out / "failures.csv", failures)
    else:
        from .common import write_text

        write_text(out / "failures.csv", "record_id,stage,cell,reason\n")
    summary = dict(
        total_sources=len(records),
        independent_base_documents=len({r["sample_id"] for r in records}),
        reader_success=sum(r["reader_status"] == "SUCCESS" for r in records),
        reader_failed=sum(r["reader_status"] != "SUCCESS" for r in records),
        fully_aligned_candidates=sum(
            r["alignment_status"] == "COMPLETE_CANDIDATE" for r in records
        ),
        partially_aligned_candidates=sum(
            r["alignment_status"] == "PARTIAL_CANDIDATE" for r in records
        ),
        reviewed_records=0,
        qa_status="PENDING_REVIEW",
        experiment_status="PENDING_PROTOCOL",
        source_gold_independent_of_predictions=True,
        oracle_delivered=False,
        reader_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        reader_source_sha256={
            str(p): sha(p)
            for d in ("ai/document_reader", "ai/ocr")
            for p in Path(d).glob("*.py")
        },
        packages={
            n: version(n)
            for n in ("paddleocr", "paddlepaddle", "paddlex", "pypdfium2", "Pillow")
        },
        python=platform.python_version(),
        selection_sha256=sha(out / "selection.csv"),
        final_test_included=False,
    )
    dump(out / "summary.json", summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--base-limit", type=int)
    p.add_argument("--worker", type=Path)
    p.add_argument("--worker-output", type=Path)
    a = p.parse_args()
    if a.worker:
        worker(a.worker, a.worker_output)
    else:
        print(json.dumps(build(a.root, a.output, a.timeout, a.base_limit), indent=2))


if __name__ == "__main__":
    main()
