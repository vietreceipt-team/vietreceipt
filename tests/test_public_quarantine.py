"""Rejected inputs remain auditable and cannot be paired with a different export."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.data.common import dump, sha
from scripts.data.quarantine_public import quarantine


class PublicQuarantineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "source.png").write_bytes(b"source image fixture")
        self.input = self.root / "export.jsonl"
        self.input.write_text(
            json.dumps(
                dict(
                    id="native-1",
                    split="train",
                    image_path="source.png",
                    annotation={"amount": "ambiguous"},
                )
            )
            + "\n",
            encoding="utf-8",
        )
        self.report = self.root / "report.json"
        self.data = dict(
            family="fixture",
            snapshot="pinned-fixture",
            source="fixture",
            license_access="fixture",
            mapping_version="fixture-1",
            input_sha256=sha(self.input),
            usable_samples=0,
            rejected=[dict(line=1, error="ambiguous amount")],
        )

    def run_quarantine(self):
        dump(self.report, self.data)
        return quarantine(self.input, self.root, self.report, self.root / "quarantine")

    def test_native_labels_image_and_reason_preserved(self):
        result = self.run_quarantine()
        record = result["records"][0]
        self.assertEqual(
            (self.root / "quarantine" / record["native_record_path"]).read_bytes(),
            self.input.read_bytes(),
        )
        self.assertEqual(record["source_image_sha256"], sha(self.root / "source.png"))
        self.assertEqual(record["original_sample_id"], "native-1")
        self.assertEqual(record["reason"], "ambiguous amount")
        self.assertFalse(result["gold_generated"])

    def test_wrong_export_hash_rejected(self):
        self.data["input_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.run_quarantine()

    def test_unaccounted_cohort_rejected(self):
        self.data["usable_samples"] = 1
        with self.assertRaises(ValueError):
            self.run_quarantine()

    def test_missing_image_retains_record_and_reports_failure(self):
        (self.root / "source.png").unlink()
        result = self.run_quarantine()
        self.assertEqual(result["quarantined_records"], 1)
        self.assertEqual(result["retention_failures"], 1)
        self.assertTrue(result["records"][0]["native_record_sha256"])

    def test_duplicate_rejection_lines_rejected(self):
        self.data["rejected"] *= 2
        with self.assertRaises(ValueError):
            self.run_quarantine()


if __name__ == "__main__":
    unittest.main()
