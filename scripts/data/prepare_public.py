"""Preserve native annotations and conservatively map an authorized JSONL export.

Input records: id, split (official), image_path, annotation (native JSON).
CORD annotation is the original ground_truth/gt_parse object; Vietnamese bill is
the native conversations object; SROIE is the original task-3 key/value object.
No OCR transcription is fabricated from sparse KIE annotations.
"""

import argparse
import json
import shutil
import uuid
from pathlib import Path
from .common import HEADERS, LINE_FIELDS, cell, dump, resolve, sha, write_csv

VERSION = "public-mapping-0.1"


def vnd_money(value):
    """This mapping version explicitly accepts dot OR comma grouped integer VND."""
    import re

    text = str(value).strip().replace(" ", "")
    if re.fullmatch(r"\d+", text):
        return int(text)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        return int(text.replace(".", ""))
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", text):
        return int(text.replace(",", ""))
    raise ValueError("Ambiguous/non-integer VND amount: " + text)


def amount(value, decimal_mark="."):
    if value is None:
        return None
    text = str(value).strip().replace(" ", "")
    # Conservative locale-specific parsing; reject currency signs/ambiguous values.
    import re
    from decimal import Decimal

    thousands = "," if decimal_mark == "." else "."
    if thousands in text:
        if not re.fullmatch(
            r"\d{1,3}(?:"
            + re.escape(thousands)
            + r"\d{3})+(?:"
            + re.escape(decimal_mark)
            + r"\d+)?",
            text,
        ):
            raise ValueError("Ambiguous numeric grouping: " + text)
        text = text.replace(thousands, "")
    text = text.replace(decimal_mark, ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        raise ValueError("Unsupported numeric value: " + text)
    v = Decimal(text)
    return int(v) if v == v.to_integral_value() else float(v)


def map_native(family, native):
    fields = {k: cell() for k in HEADERS}
    lines = []
    supported = []
    if family == "sroie":
        for source, target in (
            ("company", "seller_name"),
            ("address", "seller_address"),
        ):
            if native.get(source):
                fields[target] = cell(native[source])
                supported.append(target)
        # Date format/currency are not inferred from a dataset's country.
        if native.get("total") is not None:
            fields["total_amount"] = cell(amount(native["total"]))
            supported.append("total_amount")
    elif family == "cord":
        native = json.loads(native) if isinstance(native, str) else native
        parsed = native.get("gt_parse", native)
        menu = parsed.get("menu", [])
        if isinstance(menu, dict):
            menu = [menu]
        for index, row in enumerate(menu):
            mapped = {k: cell() for k in LINE_FIELDS}
            for source, target in (
                ("nm", "description"),
                ("cnt", "quantity"),
                ("unitprice", "unit_price"),
                ("price", "amount"),
            ):
                if row.get(source) is not None:
                    raw = row[source]
                    if target == "quantity":
                        import re

                        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[xX]?\s*", str(raw))
                        if not match:
                            raise ValueError("Unsupported CORD quantity: " + str(raw))
                        raw = match[1]
                    value = raw if target == "description" else amount(raw)
                    mapped[target] = cell(value)
                    supported.append("line_items." + target)
            lines.append(dict(line_id=f"L{index + 1}", **mapped))
        # CORD's menu.price is line TOTAL, never unit_price. Keep ambiguous
        # locale totals raw/native until the snapshot-specific locale is reviewed.
    elif family == "vietnamese_bill":
        if "master_data" in native:
            native_rows = native["master_data"]
        else:
            conversations = native.get("conversations", [])
            answers = [r["value"] for r in conversations if r.get("from") == "gpt"]
            if len(answers) != 1:
                raise ValueError("Expected one native assistant annotation")
            native_rows = json.loads(answers[0])
        for index, row in enumerate(native_rows):
            mapped = {k: cell() for k in LINE_FIELDS}
            for source, target in (
                ("ten_dich_vu", "description"),
                ("don_vi_tinh", "unit"),
                ("so_luong", "quantity"),
                ("don_gia", "unit_price"),
                ("thanh_tien", "amount"),
            ):
                if row.get(source) not in (None, ""):
                    value = (
                        row[source]
                        if target in ("description", "unit")
                        else vnd_money(row[source])
                        if target in ("unit_price", "amount")
                        else amount(row[source], decimal_mark=",")
                    )
                    mapped[target] = cell(value)
                    supported.append("line_items." + target)
            lines.append(dict(line_id=f"L{index + 1}", **mapped))
    else:
        raise ValueError("Unknown dataset family")
    return fields, lines, sorted(set(supported))


def prepare(family, input_path, source_root, out, snapshot, source, license_note):
    if not snapshot or not source or not license_note:
        raise ValueError("Snapshot/source/access evidence required")
    out = Path(out)
    if out.exists():
        raise ValueError("Use a new output directory")
    rows = []
    rejected = []
    seen = set()
    image_splits = {}
    for number, line in enumerate(
        Path(input_path).read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            original = str(record["id"])
            if record["id"] is None or not original.strip():
                raise ValueError("Empty native ID")
            identity = (record["split"], original)
            if identity in seen:
                raise ValueError("Duplicate original sample ID")
            seen.add(identity)
            if record["split"] not in ("train", "validation", "test"):
                raise ValueError("Native split required")
            image = resolve(source_root, record["image_path"])
            if not image.is_file():
                raise ValueError("Image missing")
            image_hash = sha(image)
            if (
                image_hash in image_splits
                and image_splits[image_hash] != record["split"]
            ):
                raise ValueError(
                    "Source image content crosses official splits; investigate snapshot"
                )
            image_splits[image_hash] = record["split"]
            fields, items, supported = map_native(family, record["annotation"])
            sid = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{family}/{snapshot}/{record['split']}/{original}",
                )
            )
            document = f"images/{sid}{image.suffix.lower()}"
            label = f"labels/{sid}.json"
            (out / "images").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(image, out / document)
            dump(out / f"native/{sid}.json", record["annotation"])
            gold = dict(
                annotation_schema_version="2.0",
                receipt_id=sid,
                dataset_family=family,
                dataset_snapshot=snapshot,
                sample_id=sid,
                synthetic=False,
                split=record["split"],
                mapping_version=VERSION,
                template_id=None,
                parent_sample_id=None,
                fields=fields,
                line_items=items,
            )
            dump(out / label, gold)
            rows.append(
                dict(
                    sample_id=sid,
                    original_sample_id=original,
                    dataset_family=family,
                    dataset_version=snapshot,
                    split=record["split"],
                    official_split=record["split"],
                    document_path=document,
                    ground_truth_path=label,
                    native_annotation_path=f"native/{sid}.json",
                    document_sha256=sha(out / document),
                    ground_truth_sha256=sha(out / label),
                    supported_fields=json.dumps(supported),
                    annotation_role="partial_public_gold_unlinked",
                    final_eligible="false",
                    source=source,
                    mapping_version=VERSION,
                )
            )
        except (ValueError, KeyError, TypeError, OSError) as exc:
            rejected.append(dict(line=number, error=str(exc)))
    if rows:
        write_csv(out / "manifest.csv", rows)
    dump(
        out / "preparation_report.json",
        dict(
            family=family,
            snapshot=snapshot,
            source=source,
            license_access=license_note,
            input_sha256=sha(input_path),
            usable_samples=len(rows),
            rejected=rejected,
            status="COMPLETED" if rows and not rejected else "NEEDS_REVIEW",
            metrics_eligible_fields_only=True,
        ),
    )
    return rows, rejected


def main(family=None):
    p = argparse.ArgumentParser(description=__doc__)
    if family is None:
        p.add_argument(
            "--family", choices=("cord", "sroie", "vietnamese_bill"), required=True
        )
    for k in ("input", "source-root", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    for k in ("snapshot", "source", "license-note"):
        p.add_argument("--" + k, required=True)
    a = p.parse_args()
    rows, rejected = prepare(
        family or a.family,
        a.input,
        a.source_root,
        a.out,
        a.snapshot,
        a.source,
        a.license_note,
    )
    print(f"Prepared {len(rows)}; rejected {len(rejected)}")
    return 0 if rows and not rejected else 2


if __name__ == "__main__":
    raise SystemExit(main())
