"""Reference order sensitivity is reported separately from real recognition errors."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import jiwer

from scripts.reader_reference_order_diagnostic import diagnose, ordered_reference


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class ReferenceOrderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "paired"
        self.sources = self.root / "spec-source"
        self.manifest_path = self.root / "inputs/manifest.json"
        self.output = self.root / "diagnostic"
        self.published = "LEFT ONE\nLEFT TWO\nRIGHT ONE\nRIGHT TWO\n"
        self.row_major = "LEFT ONE RIGHT ONE LEFT TWO RIGHT TWO"
        self.parent = "VRSYN2-00004"
        self.spec = {"layout": "table_heavy", "entries": [
            {"text": "LEFT ONE", "x": 10, "y": 10},
            {"text": "LEFT TWO", "x": 10, "y": 30},
            {"text": "RIGHT ONE", "x": 100, "y": 10},
            {"text": "RIGHT TWO", "x": 100, "y": 30},
        ]}
        self.spec_path = self.sources / f"render_specs/{self.parent}.json"
        write_json(self.spec_path, self.spec)
        write_json(self.sources / "reconstruction.json", {"source_commit": "a" * 40})
        transcript = self.manifest_path.parent / f"transcripts/{self.parent}.txt"
        transcript.parent.mkdir(parents=True)
        transcript.write_bytes(self.published.encode())
        self.manifest = {"split": "validation", "source_provenance": {"source_commit": "a" * 40}, "samples": []}
        self.predictions = {"clean": self.row_major, "glyph_error": self.row_major.replace("ONE", "OME", 1), "failure": ""}
        for sid in self.predictions:
            self.manifest["samples"].append({
                "id": sid, "parent_sample_id": self.parent, "source_split": "validation",
                "layout_id": "table_heavy", "transcript_path": f"transcripts/{self.parent}.txt",
                "transcript_sha256": sha(self.published.encode()), "reference": self.published,
                "input_sha256": sha(sid.encode()), "receipt_id": "receipt-" + sid,
                "condition": "clean_text_pdf" if sid != "failure" else "corrupt_pdf",
            })
        write_json(self.manifest_path, self.manifest)
        self.handoff = {"manifest_sha256": sha(self.manifest_path.read_bytes()), "samples": []}
        for mode in ("ocr_all", "route_aware"):
            metrics = {"samples": []}
            for sample in self.manifest["samples"]:
                sid, prediction = sample["id"], self.predictions[sample["id"]]
                metrics["samples"].append({
                    "id": sid, "status": "failed" if sid == "failure" else "ok",
                    "input_sha256": sample["input_sha256"],
                    "cer": jiwer.cer(" ".join(self.published.split()), prediction),
                    "wer": jiwer.wer(" ".join(self.published.split()), prediction),
                })
                if sid == "failure":
                    continue
                evidence = {"receipt_id": sample["receipt_id"], "ocr_run_id": mode + sid,
                            "pages": [{"evidence": {"blocks": [{"text": prediction}]}}]}
                path = self.run / mode / "predictions" / (sid + ".json")
                write_json(path, evidence)
                self.handoff["samples"].append({
                    "id": sid, "mode": mode, "input_sha256": sample["input_sha256"],
                    "receipt_id": sample["receipt_id"], "ocr_run_id": evidence["ocr_run_id"],
                    "evidence_path": path.relative_to(self.run).as_posix(),
                    "evidence_sha256": sha(path.read_bytes()),
                })
            write_json(self.run / mode / "metrics.json", metrics)
        write_json(self.run / "handoff.json", self.handoff)

    def run_diagnostic(self):
        return diagnose(self.run, self.manifest_path, self.sources, self.output)

    def test_panel_order_isolated_without_erasing_actual_errors_or_failures(self):
        before = {str(p): p.read_bytes() for p in self.run.rglob("*") if p.is_file()}
        result = self.run_diagnostic()
        self.assertEqual(len(result["samples"]), 6)
        self.assertTrue(result["primary_metrics_unchanged"])
        self.assertFalse(result["human_verified"])
        rows = {r["id"]: r for r in result["samples"] if r["mode"] == "route_aware"}
        self.assertGreater(rows["clean"]["original_cer"], 0)
        self.assertEqual(rows["clean"]["row_major_cer"], 0)
        self.assertEqual(rows["clean"]["row_major_wer"], 0)
        self.assertGreater(rows["glyph_error"]["row_major_cer"], 0)
        self.assertGreater(rows["glyph_error"]["row_major_wer"], 0)
        self.assertEqual(rows["failure"]["original_cer"], 1)
        self.assertEqual(rows["failure"]["row_major_cer"], 1)
        self.assertEqual(rows["failure"]["row_major_wer"], 1)
        self.assertEqual(result["slices"]["route_aware"]["all"]["samples"], 3)
        self.assertEqual(result["slices"]["route_aware"]["all"]["failures"], 1)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.run.rglob("*") if p.is_file()})
        self.assertTrue((self.output / "reference-order.csv").is_file())

    def test_changed_source_text_cannot_be_presented_as_order_only(self):
        self.spec["entries"][0]["text"] = "CORRECTED USING OCR"
        write_json(self.spec_path, self.spec)
        with self.assertRaisesRegex(ValueError, "multiset"):
            self.run_diagnostic()
        self.assertFalse(self.output.exists())

    def test_nonfinite_geometry_and_layout_mismatch_are_rejected(self):
        self.spec["entries"][0]["x"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            ordered_reference(self.spec, self.published, "table_heavy")
        self.spec["entries"][0]["x"] = 10
        with self.assertRaisesRegex(ValueError, "layout"):
            ordered_reference(self.spec, self.published, "different-layout")

    def test_stable_tied_coordinates_preserve_source_entry_order(self):
        self.spec["entries"][2]["x"] = 10
        result = ordered_reference(self.spec, self.published, "table_heavy")
        self.assertEqual(result.splitlines()[:2], ["LEFT ONE", "RIGHT ONE"])

    def test_missing_failure_record_cannot_improve_supplemental_denominator(self):
        path = self.run / "route_aware/metrics.json"
        metrics = json.loads(path.read_text())
        metrics["samples"] = metrics["samples"][:-1]
        write_json(path, metrics)
        with self.assertRaisesRegex(ValueError, "complete primary denominator"):
            self.run_diagnostic()
        self.assertFalse(self.output.exists())

    def test_changed_prediction_and_original_metrics_fail_integrity_checks(self):
        path = self.run / "ocr_all/predictions/clean.json"
        path.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "evidence checksum"):
            self.run_diagnostic()
        self.assertFalse(self.output.exists())

    def test_changed_primary_metrics_cannot_be_replaced_by_diagnostic(self):
        path = self.run / "ocr_all/metrics.json"
        metrics = json.loads(path.read_text())
        metrics["samples"][0]["cer"] = 0
        write_json(path, metrics)
        with self.assertRaisesRegex(ValueError, "primary metrics differ"):
            self.run_diagnostic()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
