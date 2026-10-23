"""Cross-module TV2 invariants and reproducibility, without mocked OCR claims."""

import json
import tempfile
import unittest
from pathlib import Path
from scripts.data.common import HEADERS, sha
from scripts.data.generate_synthetic import generate
from scripts.data.augment_dataset import augment
from scripts.data.prepare_public import amount, map_native
from scripts.data.freeze_dataset import freeze
from scripts.data.split_dataset import split


class TV2DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / "one"
        cls.rows = generate(cls.root, 6)
        cls.variants = augment(cls.root, scale=1)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_deterministic_pdf_labels_and_transcripts(self):
        other = Path(self.tmp.name) / "two"
        generate(other, 6)
        for row in self.rows:
            for key in ("document_path", "ground_truth_path", "transcript_path"):
                self.assertEqual(sha(self.root / row[key]), sha(other / row[key]))

    def test_variants_keep_base_split_and_unique_ids(self):
        parent = {r["sample_id"]: r for r in self.rows}
        self.assertEqual(len(self.variants), 6 * 17)
        self.assertEqual(len({r["variant_id"] for r in self.variants}), 6 * 17)
        for row in self.variants:
            self.assertEqual(row["split"], parent[row["sample_id"]]["split"])
        for name in ("train", "validation", "test"):
            manifest = json.loads(
                (self.root / f"tv3_{name}.json").read_text(encoding="utf-8")
            )
            for sample in manifest["samples"]:
                self.assertTrue((self.root / sample["path"]).is_file())
                self.assertTrue(sample["reference"])

    def test_pdf_actually_matches_visible_transcript(self):
        import pypdfium2 as pdfium

        for row in self.rows:
            with pdfium.PdfDocument(self.root / row["document_path"]) as doc:
                page = doc[0]
                tp = page.get_textpage()
                self.assertEqual(
                    "".join(tp.get_text_range().split()),
                    "".join(
                        (self.root / row["transcript_path"])
                        .read_text(encoding="utf-8")
                        .split()
                    ),
                )
                tp.close()
                page.close()

    def test_public_mapping_preserves_unavailable_fields(self):
        fields, lines, mask = map_native(
            "cord",
            {
                "gt_parse": {
                    "menu": [
                        {"nm": "RICE", "cnt": "2", "unitprice": "10", "price": "20"}
                    ]
                }
            },
        )
        self.assertEqual(set(fields), set(HEADERS))
        self.assertEqual(lines[0]["unit_price"]["normalized_value"], 10)
        self.assertEqual(lines[0]["amount"]["normalized_value"], 20)
        self.assertEqual(fields["seller_tax_id"]["annotation_status"], "UNKNOWN")
        self.assertNotIn("seller_tax_id", mask)

    def test_ambiguous_number_rejected(self):
        with self.assertRaises(ValueError):
            amount("1,23,4")

    def test_native_vietnamese_rows_empty_cells_and_money(self):
        fields, lines, mask = map_native(
            "vietnamese_bill",
            {
                "master_data": [
                    dict(
                        ten_dich_vu="Khám nội",
                        so_luong="1",
                        don_vi_tinh="",
                        don_gia="45,000",
                        thanh_tien="45.000",
                    )
                ]
            },
        )
        self.assertEqual(lines[0]["amount"]["normalized_value"], 45000)
        self.assertEqual(lines[0]["unit_price"]["normalized_value"], 45000)
        self.assertEqual(lines[0]["unit"]["annotation_status"], "UNKNOWN")

    def test_refuse_overwrite_and_split_after_augmentation(self):
        with self.assertRaises(ValueError):
            generate(self.root, 6)
        with self.assertRaises(ValueError):
            split(self.variants, {"corporate": "test"})

    def test_final_freeze_rejects_unreviewed_development(self):
        with self.assertRaises(ValueError):
            freeze(self.root / "manifest.csv", self.root, {}, self.root / "final.json")

    def test_real_reader_and_kie_text_pdf(self):
        from scripts.data.reader_smoke import run

        report = run(self.root, Path(self.tmp.name) / "reader")
        self.assertEqual(report[0]["status"], "PASSED", report)
        self.assertEqual(report[0]["page_sources"], ["PDF_TEXT"])
        self.assertIsNone(report[0]["accuracy"])

    def test_reviewed_link_copy_preserves_source_and_rejects_unknown_blocks(self):
        import copy
        from scripts.data.link_evidence import link
        from tests.test_kie_v2_evaluation import gold_fixture
        from tests.kie_v2_fixtures import invoice

        # Test-only approval metadata; never written into a real dataset.
        expected = gold_fixture()
        source = copy.deepcopy(expected)
        pairs = [("fields." + k, c) for k, c in source["fields"].items()]
        pairs += [
            (f"line_items.{n}.{k}", row[k])
            for n, row in enumerate(source["line_items"])
            for k in ("description", "unit", "quantity", "unit_price", "amount")
        ]
        links = {key: list(c["source_block_ids"]) for key, c in pairs}
        for key, c in pairs:
            c["source_block_ids"] = []
        review = dict(
            approved=True,
            reviewed_by="unit-test-double",
            reviewed_at="2026-10-23T00:00:00Z",
            links=links,
        )
        self.assertEqual(link(source, invoice(), review), expected)
        self.assertEqual(source["fields"]["currency"]["source_block_ids"], [])
        review["links"]["fields.currency"] = ["invented"]
        with self.assertRaises(ValueError):
            link(source, invoice(), review)
        with self.assertRaises(ValueError):
            link(source, invoice(), {})

    def test_evaluation_tables_preserve_nested_cells_and_waiting(self):
        from scripts.data.common import dump
        from scripts.data.evaluation_tables import tables

        path = Path(self.tmp.name) / "unit-report.json"
        report = dict(
            status="COMPLETED",
            dataset_family="unit-only",
            dataset_snapshot="1",
            split="validation",
            template_regime="test-double",
            manifest_sha256="unit-hash",
            git_commit="unit-commit",
            configuration={"name": "unit"},
            evaluator_version="1",
            evaluated=1,
            metrics={"line_items": {"cells": {"amount": {"exact_match": 1.0}}}},
        )
        dump(path, report)
        rows, waiting = tables([path], Path(self.tmp.name) / "unit-tables")
        self.assertEqual(rows[0]["section"], "line_items.cells.amount")
        self.assertFalse(waiting)
        dump(path, {"status": "WAITING_FOR_VERIFIED_V2_GOLD", "metrics": None})
        rows, waiting = tables([path], Path(self.tmp.name) / "unit-waiting")
        self.assertFalse(rows)
        self.assertTrue(waiting)

    def test_partial_public_mask_excludes_unsupported_headers(self):
        from scripts.data.common import cell, dump
        from scripts.data.evaluate_partial_public import evaluate
        from ai.kie.v2 import extract_invoice
        from tests.kie_v2_fixtures import invoice, KIE_RUN
        from tests.test_kie_v2_evaluation import gold_fixture

        # Entirely artificial test doubles, not a public dataset experiment.
        source = invoice()
        gold = gold_fixture()
        gold["synthetic"] = False
        gold["fields"]["seller_tax_id"] = cell()
        base = Path(self.tmp.name) / "public-unit-only"
        base.mkdir()

        def artifact(name, value):
            dump(base / name, value)
            return {"path": name, "sha256": sha(base / name)}

        record = dict(
            qa_status="VERIFIED",
            reviewed_by="unit-test-double",
            gold=artifact("gold.json", gold),
            evidence=artifact("evidence.json", source),
            prediction=artifact(
                "prediction.json", extract_invoice(source, kie_run_id=KIE_RUN)
            ),
            supported_fields=["seller_name"],
        )
        manifest = dict(
            purpose="development",
            dataset_family=gold["dataset_family"],
            dataset_snapshot=gold["dataset_snapshot"],
            split=gold["split"],
            template_regime="unit-double",
            records=[record],
        )
        dump(base / "manifest.json", manifest)
        report = evaluate(base / "manifest.json")
        self.assertEqual(report["status"], "COMPLETED", report)
        self.assertEqual(set(report["metrics"]["headers"]), {"seller_name"})
        self.assertIsNone(report["metrics"]["complete_canonical_invoice_accuracy"])
        record["qa_status"] = "PENDING"
        dump(base / "manifest.json", manifest)
        self.assertIsNone(evaluate(base / "manifest.json")["metrics"])

    def test_native_ids_are_scoped_by_official_split_and_content_leakage_rejected(self):
        from PIL import Image
        from scripts.data.common import write_text
        from scripts.data.prepare_public import prepare

        base = Path(self.tmp.name) / "import-test-double"
        base.mkdir()
        Image.new("RGB", (10, 10), "white").save(base / "train.png")
        Image.new("RGB", (10, 10), "black").save(base / "test.png")
        records = [
            dict(
                id="0",
                split=s,
                image_path=s + ".png",
                annotation={"company": "UNIT-ONLY"},
            )
            for s in ("train", "test")
        ]
        path = base / "native.jsonl"
        write_text(path, "".join(json.dumps(r) + "\n" for r in records))
        rows, rejected = prepare(
            "sroie", path, base, base / "mapped", "unit", "unit-source", "test-double"
        )
        self.assertFalse(rejected)
        self.assertNotEqual(rows[0]["sample_id"], rows[1]["sample_id"])
        records[1]["image_path"] = "train.png"
        write_text(path, "".join(json.dumps(r) + "\n" for r in records))
        rows, rejected = prepare(
            "sroie", path, base, base / "leak", "unit", "unit-source", "test-double"
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("crosses official splits", rejected[0]["error"])


if __name__ == "__main__":
    unittest.main()
