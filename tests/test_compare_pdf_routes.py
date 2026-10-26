"""Test paired accounting with a fake OCR; these are not OCR quality scores."""

import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.document_reader import DocumentReader, ReaderConfig
from ai.ocr.pipeline import OCRPipeline
from scripts.compare_pdf_routes import compare, error_examples, read_json
from scripts.benchmark_document_reader import load_manifest
from scripts.benchmark_document_reader import benchmark as real_benchmark
from scripts.create_document_fixtures import make_text_pdf
from tests.test_document_reader import Engine


class CompareTests(unittest.TestCase):
    def manifest(self, root):
        (root / "text.pdf").write_bytes(make_text_pdf(["INVOICE DEMONSTRATION ABCDEFG 123456789"]))
        (root / "bad.pdf").write_bytes(b"%PDF-1.7 broken")
        manifest = {"dataset": "test-only-fake-ocr", "version": "1", "split": "development",
                    "samples": [{"id": "text", "path": "text.pdf", "condition": "text_pdf",
                                 "reference": "INVOICE DEMONSTRATION ABCDEFG 123456789"},
                                {"id": "bad", "path": "bad.pdf", "reference": "ABC"}]}
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_pair_routes_failures_identity_and_confidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.manifest(root)
            source = read_json(manifest)
            source["source_provenance"] = {"source_commit": "example-upstream-commit"}
            source["samples"][0].update(
                sample_id="parent-1", source_split="validation", reference_status="synthetic_unreviewed")
            manifest.write_text(json.dumps(source), encoding="utf-8")
            output = root / "run"
            rows = compare(manifest, output, ReaderConfig(orientation="none"),
                           reader_factory=lambda config: DocumentReader(config=config, ocr=OCRPipeline(Engine())))
            self.assertEqual(rows[0]["route_aware_cer"], 0)
            self.assertGreater(rows[0]["ocr_all_cer"], 0)
            self.assertEqual(rows[1]["route_aware_cer"], 1)
            self.assertEqual(rows[1]["ocr_all_cer"], 1)
            handoff = read_json(output / "handoff.json")["samples"]
            self.assertEqual(handoff[0]["receipt_id"], handoff[1]["receipt_id"])
            self.assertNotEqual(handoff[0]["ocr_run_id"], handoff[1]["ocr_run_id"])
            self.assertEqual(handoff[0]["source_provenance"]["sample_id"], "parent-1")
            envelope = read_json(output / "handoff.json")
            self.assertEqual(envelope["source_provenance"], source["source_provenance"])
            self.assertEqual((output / envelope["input_manifest_path"]).resolve(), manifest.resolve())
            metadata = read_json(output / "route_aware/predictions/text.metadata.json")["pages"][0]
            self.assertEqual(metadata["source"], "PDF_TEXT")
            self.assertFalse(metadata["fallback"])
            self.assertEqual(metadata["confidence_semantics"], "not_applicable_legacy_sentinel_1")
            self.assertTrue(all(v >= 0 for v in metadata["stage_latency_ms"].values()))
            report = read_json(output / "comparison.json")
            self.assertEqual(report["slices"]["route_aware"]["all"]["failures"], 1)
            summary = report["paired_pdf_summary"]
            self.assertEqual(summary["sample_count"], 2)
            for mode in ("ocr_all", "route_aware"):
                self.assertEqual(summary["modes"][mode]["attempted"], 2)
                self.assertEqual(summary["modes"][mode]["failed"], 1)
                self.assertEqual(summary["modes"][mode]["referenced"], 2)
                self.assertGreater(summary["modes"][mode]["wer"], 0)
                self.assertGreater(summary["modes"][mode]["wall_ms_total"], 0)
            self.assertEqual(summary["modes"]["route_aware"]["pdf_text_pages"], 1)
            self.assertEqual(summary["modes"]["ocr_all"]["pdf_text_pages"], 0)
            self.assertEqual(handoff[0]["metadata_sha256"], hashlib.sha256(
                (output / handoff[0]["metadata_path"]).read_bytes()).hexdigest())
            self.assertEqual(envelope["manifest_sha256"], hashlib.sha256(manifest.read_bytes()).hexdigest())
            with self.assertRaises(FileExistsError):
                compare(manifest, output, ReaderConfig(orientation="none"))

    def test_ocr_all_bypasses_unreadable_text_layer(self):
        reader = DocumentReader(config=ReaderConfig(orientation="none", force_pdf_ocr=True),
                                ocr=OCRPipeline(Engine()))
        from uuid import uuid4
        with patch.object(reader, "_pdf_text", side_effect=AssertionError("must not extract")):
            _, audit = reader.process_with_metadata(make_text_pdf(), content_type="application/pdf",
                                                    receipt_id=uuid4(), ocr_run_id=uuid4())
        page = audit["pages"][0]
        self.assertEqual(page["routing_reason"], "forced_ocr")
        self.assertFalse(page["fallback"])

    def test_scan_fallback_is_explicit(self):
        from scripts.create_document_fixtures import scan_pdf
        from PIL import Image
        from uuid import uuid4
        reader = DocumentReader(config=ReaderConfig(orientation="none"), ocr=OCRPipeline(Engine()))
        _, audit = reader.process_with_metadata(scan_pdf(Image.new("RGB", (640, 820), "white")),
                                                content_type="application/pdf", receipt_id=uuid4(), ocr_run_id=uuid4())
        self.assertTrue(audit["pages"][0]["fallback"])
        self.assertEqual(audit["pages"][0]["routing_reason"], "unusable_text_layer")

    def test_manifest_escape_and_final_test_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.manifest(root)
            data = read_json(path)
            data["samples"][0]["path"] = "../private.pdf"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_manifest(path)
            data["samples"][0]["path"] = "text.pdf"
            data["split"] = "test"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                compare(path, root / "run", ReaderConfig())
            self.assertFalse((root / "run").exists())

    def test_diacritic_diff_keeps_actual_block_reference(self):
        block = {"text": "Hoa", "block_id": "p0_b000000", "reading_order": 0,
                 "polygon": [{"x": 0, "y": 0}] * 4}
        errors = error_examples("Hoá", {"pages": [{"page_index": 0, "evidence": {"blocks": [block]}}]})
        self.assertEqual(errors[0]["category"], "diacritics")
        self.assertEqual(errors[0]["evidence"][0]["block_id"], block["block_id"])

    def test_manifest_checksum_detects_changed_source_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.manifest(root)
            data = read_json(path)
            data["samples"][0]["input_sha256"] = hashlib.sha256((root / "text.pdf").read_bytes()).hexdigest()
            path.write_text(json.dumps(data), encoding="utf-8")
            (root / "text.pdf").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                compare(path, root / "run", ReaderConfig())
            self.assertFalse((root / "run").exists())

    def test_reference_mutation_between_modes_cannot_publish_a_pair(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.manifest(root)

            def changed_reference(*args, **kwargs):
                result = real_benchmark(*args, **kwargs)
                data = read_json(manifest)
                data["samples"][0]["reference"] = "different reference without changing input bytes"
                manifest.write_text(json.dumps(data), encoding="utf-8")
                return result

            with patch("scripts.compare_pdf_routes.benchmark", side_effect=changed_reference):
                with self.assertRaisesRegex(ValueError, "Manifest/reference changed"):
                    compare(manifest, root / "run", ReaderConfig(orientation="none"),
                            reader_factory=lambda config: DocumentReader(config=config, ocr=OCRPipeline(Engine())))
            self.assertFalse((root / "run/comparison.json").exists())
            self.assertFalse((root / "run/route_aware").exists())

    def test_pdf_with_null_reference_retains_unscored_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.manifest(root)
            data = read_json(manifest)
            for sample in data["samples"]:
                sample["reference"] = None
            manifest.write_text(json.dumps(data), encoding="utf-8")
            rows = compare(manifest, root / "run", ReaderConfig(orientation="none"),
                           reader_factory=lambda config: DocumentReader(config=config, ocr=OCRPipeline(Engine())))
            self.assertEqual(rows[1]["route_aware_status"], "failed")
            for mode in ("ocr_all", "route_aware"):
                summary = read_json(root / "run/comparison.json")["paired_pdf_summary"]["modes"][mode]
                self.assertEqual(summary["referenced"], 0)
                self.assertIsNone(summary["cer"])
                self.assertIsNone(summary["wer"])
                self.assertEqual(summary["attempted"], 2)
                self.assertEqual(summary["failed"], 1)

    def test_declared_transcript_must_match_inline_reference_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.manifest(root)
            data = read_json(manifest)
            transcript = root / "transcript.txt"
            transcript.write_bytes(data["samples"][0]["reference"].encode("utf-8"))
            data["samples"][0].update(transcript_path="transcript.txt", transcript_sha256=hashlib.sha256(transcript.read_bytes()).hexdigest())
            for change in ("inline", "file", "escape"):
                altered = json.loads(json.dumps(data))
                if change == "inline":
                    altered["samples"][0]["reference"] = "edited inline only"
                elif change == "file":
                    transcript.write_bytes(b"edited file only")
                else:
                    altered["samples"][0]["transcript_path"] = "../outside.txt"
                manifest.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaises(ValueError):
                    compare(manifest, root / "run", ReaderConfig())
                self.assertFalse((root / "run").exists())
            transcript.write_bytes(data["samples"][0]["reference"].encode("utf-8"))
            manifest.write_text(json.dumps(data), encoding="utf-8")
            rows = compare(manifest, root / "valid", ReaderConfig(orientation="none"),
                           reader_factory=lambda config: DocumentReader(config=config, ocr=OCRPipeline(Engine())))
            self.assertEqual(rows[0]["route_aware_cer"], 0)


if __name__ == "__main__":
    unittest.main()
