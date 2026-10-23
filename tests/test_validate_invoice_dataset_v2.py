"""Dataset corruption must be caught before TV3/TV4 consume it."""

import json
import tempfile
import unittest
from pathlib import Path
from scripts.data.common import dump, sha, write_csv
from scripts.data.generate_synthetic import generate
from scripts.data.validate_ground_truth import audit


class DatasetAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "dataset"
        self.rows = generate(self.root, 6)

    def check(self):
        write_csv(self.root / "manifest.csv", self.rows)
        return audit(self.root / "manifest.csv", self.root)

    def mutate_gold(self, fn):
        row = self.rows[0]
        path = self.root / row["ground_truth_path"]
        gold = json.loads(path.read_text(encoding="utf-8"))
        fn(gold)
        dump(path, gold)
        row["ground_truth_sha256"] = sha(path)

    def test_valid_manifest(self):
        self.assertEqual(self.check()["status"], "PASSED")

    def test_layout_crosses_splits(self):
        self.rows[3]["layout_id"] = self.rows[0]["layout_id"]
        self.assertIn("multiple splits", str(self.check()["errors"]))

    def test_missing_header_field(self):
        self.mutate_gold(lambda g: g["fields"].pop("currency"))
        self.assertIn("header fields missing", str(self.check()["errors"]))

    def test_parent_leakage(self):
        self.rows[3]["parent_sample_id"] = self.rows[0]["sample_id"]
        self.assertIn("crosses splits", str(self.check()["errors"]))

    def test_arithmetic_corruption(self):
        self.mutate_gold(
            lambda g: g["line_items"][0]["amount"].update(normalized_value=123)
        )
        self.assertIn("quantity * unit_price", str(self.check()["errors"]))

    def test_visible_unit_cannot_be_changed_in_gold(self):
        self.mutate_gold(lambda g: g["line_items"][0]["unit"].update(raw_value="BAD"))
        self.assertIn("visible-vs-gold", str(self.check()["errors"]))

    def test_checksum_and_broken_file(self):
        (self.root / self.rows[0]["document_path"]).write_bytes(b"broken")
        result = self.check()
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("checksum", str(result["errors"]))

    def test_duplicate_sample(self):
        self.rows.append(dict(self.rows[0]))
        self.assertIn("repeated", str(self.check()["errors"]))

    def test_path_escape(self):
        self.rows[0]["document_path"] = "../outside.pdf"
        self.assertIn("escapes", str(self.check()["errors"]))


if __name__ == "__main__":
    unittest.main()
