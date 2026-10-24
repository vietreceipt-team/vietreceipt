"""Published TV2 intake preserves selection, input bytes and pending review gates."""

import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from scripts.prepare_tv2_v2_reader_manifest import VARIANTS, digest, prepare


COMMIT = "89281198ebaf419e511b4c99321ca3355e94fcf1"


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


class PublishedTV2IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "tv2.zip"
        self.package = self.root / "package.json"
        self.registry = self.root / "base.csv"
        self.transcripts = self.root / "sources"
        self.output = self.root / "prepared"
        self.members = {}
        self.base_rows, self.selection, self.records = [], [], []
        self.source_receipt = str(uuid4())
        self.reference = "VISIBLE SOURCE TEXT\nnot an OCR prediction\n"
        for index, template, split in ((1, "corporate", "train"), (2, "table_heavy", "validation"), (3, "minimal", "test")):
            parent = f"VRSYN2-{index:05d}"
            gold = json_bytes({
                "sample_id": parent, "template_id": template, "split": split,
                "dataset_snapshot": "0.2.0", "synthetic": True,
                "receipt_id": self.source_receipt if split == "validation" else str(uuid4()),
                "fields": {"seller_name": {"raw_value": "KIE LABEL IS NOT TRANSCRIPT"}},
            })
            original = (parent + " pdf bytes").encode()
            reference = self.reference.encode() if split == "validation" else parent.encode()
            base = {
                "sample_id": parent, "base_document_id": parent, "original_sample_id": parent,
                "dataset_family": "vietreceipt_synthetic", "dataset_version": "0.2.0",
                "synthetic": "true", "split": split, "template_id": template, "layout_id": template,
                "final_eligible": "false", "ground_truth_sha256": digest(gold),
                "document_sha256": digest(original), "transcript_sha256": digest(reference),
                "transcript_path": f"transcripts/{parent}.txt",
            }
            self.base_rows.append(base)
            if split == "test":
                continue  # Held-out assets do not exist and must never be opened.
            for variant, (kind, augmentation, suffix) in VARIANTS.items():
                sid = parent + "__" + variant
                source = original if kind == "text_pdf" else sid.encode()
                row = dict(base, variant_id=sid, source_type=kind, augmentation_type=augmentation,
                           parent_sample_id=parent, document_sha256=digest(source),
                           document_path=f"rendered/{sid}{suffix}",
                           render_spec_path=f"render_specs/{parent}.json")
                self.selection.append(row)
                if split != "validation":
                    continue  # Train assets also do not exist.
                source_name = f"records/{sid}/source{suffix}"
                gold_name = f"records/{sid}/source-gold.json"
                regions_name = f"records/{sid}/source-regions.json"
                row_regions_name = f"records/{sid}/source-row-regions.json"
                self.members.update({source_name: source, gold_name: gold,
                                     regions_name: b"[]", row_regions_name: b"[]"})
                record = dict(row, sample_id=sid, record_id=sid,
                              parent_sample_id=parent, source_sample_id=parent,
                              document_sha256=digest(source), qa_status="PENDING_REVIEW",
                              source_receipt_id=self.source_receipt,
                              receipt_id=str(uuid5(UUID(self.source_receipt), sid)))
                for name, path in (("source", source_name), ("source_gold", gold_name),
                                   ("source_regions", regions_name), ("source_row_regions", row_regions_name)):
                    record[name] = {"path": path, "sha256": digest(self.members[path])}
                self.records.append(record)
            target = self.transcripts / base["transcript_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(reference)
        self.manifest = {
            "split": "validation", "synthetic": True, "qa_status": "PENDING_REVIEW",
            "dataset_family": "vietreceipt_synthetic", "dataset_snapshot": "0.2.0",
            "sample_count": 4, "base_sample_count": 1, "records": self.records,
        }
        self.write_inputs()

    def write_inputs(self):
        self.registry.write_bytes(csv_bytes(self.base_rows))
        self.members["validation-manifest.json"] = json_bytes(self.manifest)
        self.members["selection.csv"] = csv_bytes(self.selection)
        with zipfile.ZipFile(self.archive, "w") as archive:
            for name, data in self.members.items():
                archive.writestr(name, data)
        self.package.write_bytes(json_bytes({
            "archive_sha256": digest(self.archive.read_bytes()), "bytes": self.archive.stat().st_size,
            "summary": {
                "validation_manifest_sha256": digest(self.members["validation-manifest.json"]),
                "selection_sha256": digest(self.members["selection.csv"]),
            },
        }))

    def run_prepare(self):
        return prepare(self.archive, self.package, self.registry, self.transcripts, COMMIT, self.output)

    def assert_rejected_without_output(self, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            self.run_prepare()
        self.assertFalse(self.output.exists())

    def test_full_validation_cohort_only_original_bytes_and_unreviewed_source_text(self):
        result = self.run_prepare()
        self.assertEqual(len(result["samples"]), 4)
        self.assertEqual(result["qa_status"], "PENDING_REVIEW")
        for sample in result["samples"]:
            self.assertEqual(sample["source_receipt_id"], self.source_receipt)
            self.assertNotEqual(sample["receipt_id"], self.source_receipt)
            self.assertEqual(sample["reference"], self.reference)
            self.assertNotIn("KIE LABEL", sample["reference"])
            self.assertFalse(sample["reference_provenance"]["human_verified"])
            self.assertEqual(digest((self.output / sample["path"]).read_bytes()), sample["input_sha256"])
            self.assertEqual(digest((self.output / sample["source_regions_path"]).read_bytes()), sample["source_regions_sha256"])
        self.assertEqual(len({s["receipt_id"] for s in result["samples"]}), 4)
        self.assertFalse(any("00001" in str(p) or "00003" in str(p) for p in self.output.rglob("*")))
        with self.assertRaises(FileExistsError):
            self.run_prepare()

    def test_archive_and_embedded_artifact_tampering_are_distinct_failures(self):
        original = self.archive.read_bytes()
        self.archive.write_bytes(original + b"tampered")
        self.assert_rejected_without_output("archive checksum")
        self.members[self.records[0]["source"]["path"]] += b"tampered"
        self.write_inputs()
        self.assert_rejected_without_output("artifact checksum")

    def test_transcript_tampering_does_not_become_a_new_reference(self):
        path = self.transcripts / self.base_rows[1]["transcript_path"]
        path.write_text("invented reference", encoding="utf-8")
        self.assert_rejected_without_output("transcript checksum")

    def test_missing_and_duplicate_records_cannot_shrink_denominator(self):
        original = list(self.records)
        for records in (original[:-1], original + [original[0]]):
            self.manifest["records"] = records
            self.manifest["sample_count"] = len(records)
            self.write_inputs()
            self.assert_rejected_without_output("membership")

    def test_locked_split_and_duplicate_base_content_fail_before_assets_are_opened(self):
        self.base_rows[2]["split"] = "validation"
        self.write_inputs()
        self.assert_rejected_without_output("split leakage")
        self.base_rows[2]["split"] = "test"
        self.base_rows[2]["ground_truth_sha256"] = self.base_rows[1]["ground_truth_sha256"]
        self.write_inputs()
        self.assert_rejected_without_output("Duplicated content")

    def test_input_alias_cannot_silently_replace_the_source_receipt_identity(self):
        self.records[0]["receipt_id"] = str(uuid4())
        self.write_inputs()
        self.assert_rejected_without_output("UUID.*alias")

    def test_unsafe_archive_artifact_and_transcript_paths_are_rejected(self):
        self.records[0]["source"]["path"] = "../outside.pdf"
        self.write_inputs()
        self.assert_rejected_without_output("Unsafe archive artifact")
        self.records[0]["source"]["path"] = f"records/{self.records[0]['record_id']}/source.pdf"
        self.base_rows[1]["transcript_path"] = "../outside.txt"
        self.write_inputs()
        self.assert_rejected_without_output("Unsafe repository-relative path")

    def test_pending_manifest_cannot_be_promoted_by_import(self):
        self.manifest["qa_status"] = "VERIFIED"
        self.write_inputs()
        self.assert_rejected_without_output("pending TV2")

    def test_exact_variant_binding_and_cross_split_derivative_leakage(self):
        self.records[1]["document_sha256"] = self.records[2]["document_sha256"]
        self.write_inputs()
        self.assert_rejected_without_output("exact selected variant")
        self.records[1]["document_sha256"] = self.selection[5]["document_sha256"]
        # The original base PDFs differ, but a derivative has been reused across splits.
        self.selection[0]["document_sha256"] = self.selection[5]["document_sha256"]
        self.write_inputs()
        self.assert_rejected_without_output("Derivative source content duplicated")

    def test_selection_and_manifest_pins_are_checked_separately(self):
        package = json.loads(self.package.read_text())
        for key in ("selection_sha256", "validation_manifest_sha256"):
            original = package["summary"][key]
            package["summary"][key] = "0" * 64
            self.package.write_bytes(json_bytes(package))
            self.assert_rejected_without_output("Published .* checksum")
            package["summary"][key] = original


if __name__ == "__main__":
    unittest.main()
