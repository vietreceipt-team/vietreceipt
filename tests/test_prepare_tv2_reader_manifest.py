"""TV2 import integrity, split isolation and independent-reference checks."""

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from scripts.prepare_tv2_reader_manifest import prepare, visible_svg_text


COMMIT = "5e5b871dd1c7413f2d74acc175aad0f0186486f7"


class PrepareTV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "mirror"
        self.base = self.root / "data/synthetic"
        for directory in ("documents", "labels", "rendered"):
            (self.base / directory).mkdir(parents=True)
        self.manifest = self.base / "rendered/manifest.csv"
        self.output = Path(self.temp.name) / "reader-inputs"
        self.rows = []
        self.receipt = {}
        for number, layout, split in ((1, "layout_a", "train"), (2, "layout_b", "validation"), (3, "layout_c", "test")):
            parent = f"VRSYN-{number:03d}"
            self.receipt[parent] = str(uuid4())
            label_path = self.base / "labels" / (parent + ".json")
            label_path.write_text(json.dumps({
                "receipt_id": self.receipt[parent], "sample_id": parent,
                "template_id": layout, "dataset_family": "vietreceipt_synthetic",
                "dataset_snapshot": "v0.1", "split": split, "synthetic": True,
                "mapping_version": "vietreceipt-canonical-v2",
                "fields": {"seller_name": {"raw_value": "THIS IS NOT THE TRANSCRIPT"}},
            }), encoding="utf-8")
            (self.base / "documents" / (parent + ".svg")).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><title>Not printed title</title>'
                '<text x="10" y="10">HOA DON &amp; INVOICE</text>'
                '<text x="10" y="30">Hang mot</text><text x="100" y="30">12.000</text>'
                '<text x="10" y="50">Tong: 12.000 VND</text></svg>', encoding="utf-8")
            for kind, degradation, suffix in (("vector_pdf", "clean", ".pdf"), ("png_image", "blur", ".png")):
                variant = parent + ("__vector_pdf" if kind == "vector_pdf" else "__blur")
                document = self.base / "rendered" / (variant + suffix)
                document.write_bytes(b"fake fixture bytes; importer performs no OCR")
                self.rows.append({
                    "sample_id": parent, "parent_sample_id": parent, "variant_id": variant,
                    "dataset_family": "vietreceipt_synthetic", "dataset_snapshot": "v0.1",
                    "document_path": document.relative_to(self.root).as_posix(),
                    "ground_truth_path": label_path.relative_to(self.root).as_posix(),
                    "source_type": "synthetic_svg", "synthetic": "true", "split": split,
                    "layout_id": layout, "mapping_version": "vietreceipt-canonical-v2",
                    "input_type": kind, "degradation": degradation, "quality": "clean",
                    "document_sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
                    "ground_truth_sha256": hashlib.sha256(label_path.read_bytes()).hexdigest(),
                    "provenance": "unit fixture only",
                })
        self.write_manifest()

    def write_manifest(self):
        with self.manifest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.rows[0]))
            writer.writeheader()
            writer.writerows(self.rows)

    def run_prepare(self, **kwargs):
        return prepare(self.root, self.manifest, COMMIT, self.output, **kwargs)

    def test_validation_only_independent_transcript_and_provenance(self):
        # Locked/train source assets may be unavailable and must never be read.
        for parent in ("VRSYN-001", "VRSYN-003"):
            (self.base / "documents" / (parent + ".svg")).unlink()
            (self.base / "labels" / (parent + ".json")).unlink()
        manifest = self.run_prepare()
        self.assertEqual(manifest["split"], "validation")
        self.assertEqual(len(manifest["samples"]), 2)
        self.assertEqual(manifest["provenance"]["source_commit"], COMMIT)
        self.assertEqual(manifest["provenance"]["source_manifest_sha256"], hashlib.sha256(self.manifest.read_bytes()).hexdigest())
        for sample in manifest["samples"]:
            self.assertEqual(sample["receipt_id"], self.receipt["VRSYN-002"])
            self.assertEqual(sample["reference"], "HOA DON & INVOICE\nHang mot\n12.000\nTong: 12.000 VND")
            self.assertNotIn("THIS IS NOT THE TRANSCRIPT", sample["reference"])
            self.assertFalse(sample["reference_provenance"]["human_verified"])
            self.assertIn("unreviewed", sample["reference_status"])
            self.assertEqual(sample["source"]["split"], "validation")
            self.assertEqual(hashlib.sha256((self.output / sample["path"]).read_bytes()).hexdigest(), sample["source"]["document_sha256"])
            self.assertEqual(sample["condition"], sample["source"]["input_type"] + "_" + sample["source"]["degradation"])
        self.assertEqual(len(list((self.output / "sources/labels").glob("*.json"))), 1)
        self.assertFalse(any("VRSYN-003" in p.name for p in self.output.rglob("*")))
        with self.assertRaises(FileExistsError):
            self.run_prepare()

    def test_document_and_label_tampering_fail_before_output(self):
        for key in ("document_path", "ground_truth_path"):
            with self.subTest(key=key):
                path = self.root / self.rows[2][key]
                original = path.read_bytes()
                path.write_bytes(original + b"tampered")
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    self.run_prepare()
                self.assertFalse(self.output.exists())
                path.write_bytes(original)

    def test_duplicates_and_split_leakage_anywhere_are_rejected(self):
        cases = (
            (0, "variant_id", self.rows[2]["variant_id"], "Duplicate variant"),
            (4, "split", "validation", "split leakage"),
            (1, "ground_truth_sha256", "0" * 64, "Parent metadata"),
        )
        for index, key, value, error in cases:
            with self.subTest(key=key):
                original = self.rows[index][key]
                self.rows[index][key] = value
                self.write_manifest()
                with self.assertRaisesRegex(ValueError, error):
                    self.run_prepare()
                self.assertFalse(self.output.exists())
                self.rows[index][key] = original

    def test_final_test_train_and_missing_ids_cannot_be_selected(self):
        for parent in ("VRSYN-001", "VRSYN-003", "VRSYN-999"):
            with self.subTest(parent=parent), self.assertRaisesRegex(ValueError, "final test is locked"):
                self.run_prepare(sample_ids=[parent])
        self.assertFalse(self.output.exists())

    def test_path_escape_unknown_type_and_invalid_commit_are_rejected(self):
        for key, value in (("document_path", "../outside.pdf"), ("ground_truth_path", "C:/secret.json"), ("input_type", "svg")):
            with self.subTest(key=key):
                original = self.rows[0][key]
                self.rows[0][key] = value
                self.write_manifest()
                with self.assertRaises(ValueError):
                    self.run_prepare()
                self.rows[0][key] = original
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "full 40-character"):
            prepare(self.root, self.manifest, "main", self.output)
        self.assertFalse(self.output.exists())

    def test_label_identity_and_receipt_uuid_require_real_source(self):
        path = self.root / self.rows[2]["ground_truth_path"]
        original = json.loads(path.read_text(encoding="utf-8"))
        for key, value in (("split", "test"), ("receipt_id", "placeholder")):
            with self.subTest(key=key):
                label = dict(original, **{key: value})
                path.write_text(json.dumps(label), encoding="utf-8")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                for row in self.rows[2:4]:
                    row["ground_truth_sha256"] = digest
                self.write_manifest()
                with self.assertRaises(ValueError):
                    self.run_prepare()
                self.assertFalse(self.output.exists())

    def test_hidden_or_scripted_svg_requires_manual_review(self):
        path = self.base / "documents/VRSYN-002.svg"
        for content in ('<text display="none">hidden</text>', '<script>bad()</script>', '<style>text{display:none}</style>', '<g transform="rotate(90)"><text x="1" y="1">transformed</text></g>', '<text x="1" y="1"><tspan>nested</tspan></text>'):
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg">' + content + '</svg>', encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(ValueError):
                visible_svg_text(path)

    def test_row_major_order_comes_from_source_baselines_not_dom_order(self):
        path = self.base / "documents/VRSYN-002.svg"
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg">'
                        '<text x="48" y="76">Seller</text>'
                        '<text x="48" y="118">Date</text>'
                        '<text x="430" y="76">Buyer</text></svg>', encoding="utf-8")
        self.assertEqual(visible_svg_text(path), "Seller\nBuyer\nDate")

    def test_original_svg_matches_upstream_base_manifest_checksum(self):
        base_manifest = self.base / "manifest.csv"
        base_rows = []
        for row in self.rows[::2]:
            source = dict(row)
            parent = row["sample_id"]
            svg = self.base / "documents" / (parent + ".svg")
            source["document_path"] = svg.relative_to(self.root).as_posix()
            source["document_sha256"] = hashlib.sha256(svg.read_bytes()).hexdigest()
            base_rows.append(source)
        with base_manifest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(base_rows[0]))
            writer.writeheader()
            writer.writerows(base_rows)
        svg = self.base / "documents/VRSYN-002.svg"
        original = svg.read_bytes()
        svg.write_bytes(original.replace(b"Hang mot", b"Hang gia"))
        with self.assertRaisesRegex(ValueError, "Source SVG checksum mismatch"):
            self.run_prepare()
        self.assertFalse(self.output.exists())
        svg.write_bytes(original)
        manifest = self.run_prepare()
        self.assertEqual(len(manifest["provenance"]["base_manifests"]), 1)
        report = json.loads((self.output / "prepare-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["source_svg_upstream_checksum"], "verified_against_base_manifest")


if __name__ == "__main__":
    unittest.main()
