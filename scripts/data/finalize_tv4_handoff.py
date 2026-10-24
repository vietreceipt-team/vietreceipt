"""Verify captured records, refresh alignment candidates, and publish an all-record review gallery."""

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from PIL import Image
from .common import dump, sha, write_text, write_csv
from .build_tv4_handoff import align


def finalize(root):
    root = Path(root).resolve()
    records = []
    failures = []
    gallery = []
    for split in ("train", "validation"):
        path = root / f"{split}-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for record in manifest["records"]:
            folder = root / "records" / record["record_id"]
            for key in ("source", "source_gold", "source_regions"):
                ref = record[key]
                if sha(root / ref["path"]) != ref["sha256"]:
                    raise ValueError("Source artifact changed: " + record["record_id"])
            gold = json.loads((folder / "source-gold.json").read_text(encoding="utf-8"))
            record["source_sample_id"] = gold["sample_id"]
            record["sample_id"] = record["record_id"]
            regions = json.loads(
                (folder / "source-regions.json").read_text(encoding="utf-8")
            )
            # Rows are source-defined regions; they do not disappear if OCR misses them.
            row_regions = []
            for index, line in enumerate(gold["line_items"]):
                cells = [
                    r for r in regions if r["cell"].startswith(f"line_items.{index}.")
                ]
                row_regions.append(
                    dict(
                        line_id=line["line_id"],
                        page_index=0,
                        bounds=[
                            min(r["bounds"][0] for r in cells),
                            min(r["bounds"][1] for r in cells),
                            max(r["bounds"][2] for r in cells),
                            max(r["bounds"][3] for r in cells),
                        ],
                        annotation_origin="source render geometry; independent spatial QA pending",
                    )
                )
            dump(folder / "source-row-regions.json", row_regions)
            if record["reader_status"] == "SUCCESS":
                evidence = json.loads(
                    (folder / "evidence.json").read_text(encoding="utf-8")
                )
                if sha(folder / "evidence.json") != record["evidence"]["sha256"]:
                    raise ValueError("Evidence changed")
                aligned, alignment = align(gold, regions, evidence)
                aligned["sample_id"] = record["record_id"]
                dump(folder / "aligned-gold-candidate.json", aligned)
                dump(folder / "alignment.json", alignment)
                counts = Counter(r["status"] for r in alignment)
                record["alignment_counts"] = dict(counts)
                record["alignment_status"] = (
                    "COMPLETE_CANDIDATE"
                    if not counts["UNALIGNED"]
                    and not counts["SHARED_BLOCK_REQUIRES_REVIEW"]
                    else "PARTIAL_CANDIDATE"
                )
                record["gold"]["sha256"] = sha(folder / "aligned-gold-candidate.json")
                record["aligned_gold_sha256"] = record["gold"]["sha256"]
                review_source = json.loads(json.dumps(gold))
                review_source["receipt_id"] = record["receipt_id"]
                review_source["sample_id"] = record["record_id"]
                dump(folder / "review-source-gold.json", review_source)
                dump(
                    folder / "review-template.json",
                    dict(
                        approved=False,
                        reviewed_by="",
                        reviewed_at="",
                        gold_sha256=sha(folder / "review-source-gold.json"),
                        evidence_sha256=sha(folder / "evidence.json"),
                        original_source_gold_sha256=record["source_gold"]["sha256"],
                        links={
                            r["cell"]: r["source_block_ids"] or r["candidate_block_ids"]
                            for r in alignment
                        },
                        note="Proposal only. Verify actual source/regions and every chosen block before approval. Empty/missing cells must remain unresolved, never invent IDs.",
                    ),
                )
                for cell in alignment:
                    if cell["status"] != "CANDIDATE_REQUIRES_REVIEW":
                        failures.append(
                            dict(
                                record_id=record["record_id"],
                                stage="alignment",
                                cell=cell["cell"],
                                reason=cell["reason"] or cell["status"],
                            )
                        )
            else:
                alignment = []
                failures.append(
                    dict(
                        record_id=record["record_id"],
                        stage="reader",
                        cell="",
                        reason=record.get("reader_error", "Reader failed"),
                    )
                )
            source = root / record["source"]["path"]
            if source.suffix == ".pdf":
                import pypdfium2 as pdfium

                with pdfium.PdfDocument(source) as pdf:
                    page = pdf[0]
                    bitmap = page.render(scale=1.2)
                    preview = bitmap.to_pil().convert("RGB").copy()
                    bitmap.close()
                    page.close()
            else:
                with Image.open(source) as image:
                    preview = image.convert("RGB").copy()
            preview.save(folder / "source-preview.png")

            def esc(v):
                return html.escape(str(v))

            table = "".join(
                "<tr>"
                + "".join(
                    "<td>" + esc(c) + "</td>"
                    for c in (
                        r["cell"],
                        r["source_text"],
                        r["observed_text"],
                        ", ".join(r["source_block_ids"]),
                        ", ".join(r["candidate_block_ids"]),
                        r["status"],
                    )
                )
                + "</tr>"
                for r in alignment
            )
            write_text(
                folder / "review.html",
                f"""<!doctype html><meta charset="utf-8"><title>{esc(record["record_id"])}</title>
<style>body{{font:14px system-ui;margin:24px}}img{{max-width:60vw}}td,th{{padding:8px;border:1px solid #ccc;vertical-align:top}}table{{border-collapse:collapse}}</style>
<h1>{esc(record["record_id"])}</h1><p>PENDING REVIEW. Source gold is preserved; candidate IDs are not an approval.</p>
<a href="source-gold.json">Source gold</a> | <a href="source-regions.json">Source cell regions</a> |
<a href="source-row-regions.json">Source rows</a> | <a href="evidence.json">Actual reader evidence</a> |
<a href="reader.log">All reader logs</a> | <a href="review-template.json">Pending review mapping</a><p><img src="source-preview.png" alt="Original source rendered for review"></p>
<table><tr><th>Cell</th><th>Source value</th><th>Observed OCR</th><th>Linked candidate IDs</th><th>Spatial candidate IDs</th><th>Status</th></tr>{table}</table>""",
            )
            record["source_row_regions"] = {
                "path": (folder / "source-row-regions.json")
                .relative_to(root)
                .as_posix(),
                "sha256": sha(folder / "source-row-regions.json"),
            }
            record["qa_status"] = "PENDING_REVIEW"
            record["reader_log"] = {
                "path": (folder / "reader.log").relative_to(root).as_posix(),
                "sha256": sha(folder / "reader.log"),
            }
            if record["reader_status"] == "SUCCESS":
                record["reader_metadata"] = {
                    "path": (folder / "reader-metadata.json")
                    .relative_to(root)
                    .as_posix(),
                    "sha256": sha(folder / "reader-metadata.json"),
                }
            record["mapping_version"] = "source-spatial-candidate-0.3"
            dump(folder / "record.json", record)
            records.append(record)
            gallery.append(
                f'<li><a href="records/{esc(record["record_id"])}/review.html">{esc(record["record_id"])}</a>: {esc(record["reader_status"])} / {esc(record["alignment_status"])}</li>'
            )
        manifest["artifact_hashes_frozen"] = True
        manifest["base_sample_count"] = len(
            {r["base_document_id"] for r in manifest["records"]}
        )
        manifest["manifest_qa"] = (
            "SOURCE_HASHES_AND_REAL_BLOCK_IDS_CHECKED; HUMAN_QA_PENDING"
        )
        dump(path, manifest)
    if failures:
        write_csv(root / "failures.csv", failures)
    else:
        write_text(root / "failures.csv", "record_id,stage,cell,reason\n")
    summary = json.loads((root / "summary.json").read_text())
    summary.update(
        fully_aligned_candidates=sum(
            r["alignment_status"] == "COMPLETE_CANDIDATE" for r in records
        ),
        partially_aligned_candidates=sum(
            r["alignment_status"] == "PARTIAL_CANDIDATE" for r in records
        ),
        train_manifest_sha256=sha(root / "train-manifest.json"),
        validation_manifest_sha256=sha(root / "validation-manifest.json"),
        failure_rows=len(failures),
        mapping_version="source-spatial-candidate-0.3",
        gallery_includes_all_sources=True,
    )
    dump(root / "summary.json", summary)
    write_text(
        root / "index.html",
        '<!doctype html><meta charset="utf-8"><h1>TV2 development / validation handoff</h1><p>All declared records, including failures. PENDING owner review. No final test and no oracle included.</p><ul>'
        + "".join(gallery)
        + "</ul>",
    )
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(finalize(a.root), indent=2))


if __name__ == "__main__":
    main()
