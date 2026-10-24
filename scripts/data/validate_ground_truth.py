"""Independent source-gold QA; a pass is not human review or model accuracy."""

import argparse
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image
from .common import HEADERS, LINE_FIELDS, ROOT, dump, read_csv, resolve, sha

FIELDS = frozenset(HEADERS)


def audit(manifest, root):
    errors, warnings = [], set()
    layouts, parents, hashes = defaultdict(set), defaultdict(set), defaultdict(set)
    seen, gold_seen = set(), set()
    root = Path(root).resolve()
    rows = read_csv(manifest)
    if not rows:
        return dict(
            status="FAILED", sample_count=0, errors=["Empty manifest"], warnings=[]
        )
    required = {"sample_id", "split", "layout_id", "document_path", "ground_truth_path"}
    if not required <= set(rows[0]):
        return dict(
            status="FAILED",
            sample_count=len(rows),
            errors=["Missing manifest columns"],
            warnings=[],
        )
    schema = json.loads(
        (ROOT / "schemas/invoice-annotation.v2.schema.json").read_text()
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for row in rows:
        sid = row["sample_id"]
        uid = row.get("variant_id") or sid

        def fail(message):
            errors.append(f"{uid}: {message}")

        if not uid or uid in seen:
            fail("empty or repeated sample/variant ID")
        seen.add(uid)
        if (
            row["split"] not in ("train", "validation", "test", "benchmark")
            or not row["layout_id"]
        ):
            fail("invalid split/layout")
        layouts[row["layout_id"]].add(row["split"])
        parents[row.get("base_document_id") or row.get("parent_sample_id") or sid].add(
            row["split"]
        )
        parents[sid].add(row["split"])
        if row.get("parent_sample_id"):
            parents[row["parent_sample_id"]].add(row["split"])
        try:
            doc = resolve(root, row["document_path"])
            label = resolve(root, row["ground_truth_path"])
            if not doc.is_file() or not label.is_file():
                fail("missing document/ground truth file")
                continue
            for path, key in ((doc, "document_sha256"), (label, "ground_truth_sha256")):
                if not row.get(key) or sha(path) != row[key]:
                    fail("checksum mismatch/missing: " + key)
            hashes[sha(doc)].add(row["split"])
            if doc.suffix.lower() in (".png", ".jpg", ".jpeg"):
                with Image.open(doc) as im:
                    im.verify()
            elif doc.suffix.lower() == ".pdf":
                import pypdfium2 as pdfium

                with pdfium.PdfDocument(doc) as pdf:
                    if not len(pdf):
                        fail("empty PDF")
                    elif row.get("source_type") == "text_pdf" and row.get(
                        "transcript_path"
                    ):
                        page = pdf[0]
                        textpage = page.get_textpage()
                        reference = resolve(root, row["transcript_path"]).read_text(
                            encoding="utf-8"
                        )
                        if "".join(textpage.get_text_range().split()) != "".join(
                            reference.split()
                        ):
                            fail("actual PDF text differs from source transcript")
                        textpage.close()
                        page.close()
            else:
                warnings.add(
                    "Some inputs are not upload-supported; render PDF/PNG first"
                )
            gold = json.loads(label.read_text(encoding="utf-8"))
            if (
                gold.get("sample_id") != sid
                or gold.get("split") != row["split"]
                or gold.get("template_id") != row["layout_id"]
            ):
                fail("label/manifest identity mismatch")
            for rk, gk in (
                ("dataset_family", "dataset_family"),
                ("dataset_version", "dataset_snapshot"),
                ("mapping_version", "mapping_version"),
            ):
                if row.get(rk) != gold.get(gk):
                    fail("provenance mismatch: " + rk)
            if row.get("synthetic") != str(gold.get("synthetic")).lower():
                fail("synthetic flag mismatch")
            if label in gold_seen:
                continue
            gold_seen.add(label)
            for error in validator.iter_errors(gold):
                fail("schema: " + error.message)
            fields = gold.get("fields", {})
            items = gold.get("line_items", [])
            if set(fields) != FIELDS:
                fail("header fields missing/extra")
            cells = list(fields.values()) + [
                r[k] for r in items for k in LINE_FIELDS if k in r
            ]
            for c in cells:
                if not isinstance(c, dict):
                    fail("invalid cell")
                    continue
                present = c.get("annotation_status") == "PRESENT"
                if present != (c.get("normalized_value") is not None):
                    fail("cell status/value mismatch")
                if present and not c.get("source_block_ids"):
                    warnings.add(
                        "Unlinked source gold: not eligible for evidence-linked KIE evaluation"
                    )
            ids = [i.get("line_id") for i in items]
            if len(set(ids)) != len(ids):
                fail("duplicate line IDs")

            def value(c):
                if c.get("annotation_status") != "PRESENT":
                    return None
                v = c.get("normalized_value")
                if type(v) not in (int, float):
                    raise ValueError("numeric cell is not numeric")
                d = Decimal(str(v))
                if not d.is_finite() or d < 0:
                    raise ValueError("invalid numeric value")
                return d

            amounts = []
            for item in items:
                if not set(LINE_FIELDS) <= set(item):
                    fail("missing line cells")
                    continue
                q, p, a = [value(item[k]) for k in ("quantity", "unit_price", "amount")]
                if all(v is not None for v in (q, p, a)) and abs(q * p - a) > 1:
                    fail("quantity * unit_price != amount")
                amounts.append(a)
            subtotal, tax, total = [
                value(fields.get(k, {}))
                for k in ("subtotal", "tax_amount", "total_amount")
            ]
            if (
                all(v is not None for v in (subtotal, tax, total))
                and subtotal + tax != total
            ):
                fail("subtotal + tax != total")
            if (
                subtotal is not None
                and amounts
                and all(v is not None for v in amounts)
                and sum(amounts) != subtotal
            ):
                fail("sum(line amounts) != subtotal")
            if row.get("transcript_path"):
                transcript = resolve(root, row["transcript_path"])
                if sha(transcript) != row.get("transcript_sha256"):
                    fail("transcript checksum mismatch")
                if row.get("render_spec_path"):
                    spec = json.loads(
                        resolve(root, row["render_spec_path"]).read_text(
                            encoding="utf-8"
                        )
                    )
                    entries = {e["key"]: e["text"] for e in spec["entries"]}
                    if (
                        transcript.read_text(encoding="utf-8")
                        != "\n".join(e["text"] for e in spec["entries"]) + "\n"
                    ):
                        fail("render/transcript mismatch")
                    pairs = [("fields." + k, c) for k, c in fields.items()]
                    pairs += [
                        (f"line_items.{n}.{k}", i[k])
                        for n, i in enumerate(items)
                        for k in LINE_FIELDS
                    ]
                    for key, c in pairs:
                        if (c["annotation_status"] == "PRESENT") != (key in entries):
                            fail("visible-vs-gold presence mismatch: " + key)
                        if c["annotation_status"] == "PRESENT":
                            v = c["raw_value"]
                            if (
                                key.endswith(
                                    (
                                        "unit_price",
                                        "amount",
                                        "subtotal",
                                        "tax_amount",
                                        "total_amount",
                                    )
                                )
                                and type(v) is int
                            ):
                                v = f"{v:,}".replace(",", ".")
                            if not entries.get(key, "").endswith(str(v)):
                                fail("visible-vs-gold value mismatch: " + key)
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            ImportError,
            RuntimeError,
        ) as exc:
            fail(type(exc).__name__ + ": " + str(exc))
    for name, groups in layouts.items():
        if len(groups) > 1:
            errors.append(f"layout family {name!r} occurs in multiple splits")
    for name, groups in parents.items():
        if len(groups) > 1:
            errors.append(f"parent/base {name!r} crosses splits")
    if any(len(groups) > 1 for groups in hashes.values()):
        errors.append("duplicate file content crosses splits")
    return dict(
        status="FAILED" if errors else "PASSED",
        sample_count=len(rows),
        base_sample_count=len(gold_seen),
        layout_families=len(layouts),
        errors=errors,
        warnings=sorted(warnings),
        split_counts=dict(Counter(r["split"] for r in rows)),
        verification_scope="automated source-gold QA only",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    result = audit(a.manifest, a.root)
    if a.output:
        dump(a.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
