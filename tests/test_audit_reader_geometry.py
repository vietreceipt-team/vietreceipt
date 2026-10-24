import io
import json
import hashlib
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import pypdfium2 as pdfium
from PIL import Image

from ai.document_reader import DocumentReader, ReaderConfig
from ai.ocr.pipeline import OCRPipeline
from scripts.audit_reader_geometry import audit
from scripts.create_document_fixtures import make_text_pdf


class Engine:
    """Explicit test OCR provider; source decoding/geometry are real."""

    def predict(self, image):
        height, width = image.shape[:2]
        return [{
            "rec_texts": ["INVOICE TEST"], "rec_scores": [0.9],
            "rec_polys": [[[width * 0.1, height * 0.1], [width * 0.4, height * 0.1],
                           [width * 0.4, height * 0.2], [width * 0.1, height * 0.2]]],
        }]


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GeometryAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        self.run.mkdir()
        self.manifest = self.root / "manifest.json"

    def prepare(self, data, suffix, *, orientation="none", max_side=80, orientation_model=None):
        source = self.root / ("source" + suffix)
        source.write_bytes(data)
        receipt_id = str(uuid4())
        manifest = {"dataset": "geometry-test", "version": "1", "split": "validation",
                    "samples": [{"id": "sample", "path": source.name,
                                 "input_sha256": sha(source), "receipt_id": receipt_id}]}
        write(self.manifest, manifest)
        items, result = [], {"id": "sample", "input_sha256": sha(source)}
        for mode in ("ocr_all", "route_aware"):
            reader = DocumentReader(
                config=ReaderConfig(orientation=orientation, max_side=max_side,
                                    force_pdf_ocr=mode == "ocr_all"),
                ocr=OCRPipeline(Engine()), orientation_model=orientation_model,
            )
            document, metadata = reader.process_with_metadata(
                data, content_type="application/pdf" if suffix == ".pdf" else "image/jpeg",
                receipt_id=receipt_id, ocr_run_id=uuid4())
            evidence_path = self.run / (mode + ".json")
            metadata_path = self.run / (mode + ".metadata.json")
            write(evidence_path, document)
            write(metadata_path, dict(metadata, input_sha256=sha(source)))
            items.append({"id": "sample", "mode": mode,
                          "receipt_id": receipt_id, "ocr_run_id": document["ocr_run_id"],
                          "source_path": source.name, "input_sha256": sha(source),
                          "evidence_path": evidence_path.name, "evidence_sha256": sha(evidence_path),
                          "metadata_path": metadata_path.name, "metadata_sha256": sha(metadata_path)})
            result[mode + "_status"] = "ok"
            result[mode + "_error"] = ""
        write(self.run / "handoff.json", {k: manifest[k] for k in ("dataset", "version", "split")} | {
            "samples": items, "manifest_sha256": sha(self.manifest)})
        write(self.run / "comparison.json", {"samples": [result]})

    def jpeg(self):
        stream = io.BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (120, 200), "white").save(stream, format="JPEG", exif=exif)
        return stream.getvalue()

    def update_metadata(self, change):
        handoff = json.loads((self.run / "handoff.json").read_text())
        path = self.run / handoff["samples"][0]["metadata_path"]
        metadata = json.loads(path.read_text())
        change(metadata)
        write(path, metadata)
        handoff["samples"][0]["metadata_sha256"] = sha(path)
        write(self.run / "handoff.json", handoff)

    def test_exif_resize_and_inverse_rotation_source_frame(self):
        class Orientation:
            def predict(self, image):
                return [{"label_names": ["270"], "scores": [0.99]}]

        self.prepare(self.jpeg(), ".jpg", orientation="auto", orientation_model=Orientation())
        output = self.root / "audit"
        report = audit(self.run, self.manifest, output)
        page = report["pages"][0]
        self.assertEqual((page["width_px"], page["height_px"]), (200, 120))
        self.assertEqual((page["raw_image_width_px"], page["raw_image_height_px"]), (120, 200))
        self.assertEqual(page["raw_exif_orientation"], 6)
        self.assertEqual((page["ocr_width_px_derived"], page["ocr_height_px_derived"]), (48, 80))
        self.assertEqual(page["inverse_ocr_rotation_normalized_xy"], "(y, 1-x)")
        self.assertEqual(report["audited_runs"], 2)
        self.assertEqual(report["manifest_binding"], "verified_handoff_hash")
        self.assertEqual(report["human_alignment_status"], "pending_TV2_independent_QA_and_TV4_review")
        with (output / "blocks.csv").open(encoding="utf-8") as handle:
            self.assertIn("p0_b000000", handle.read())
        with self.assertRaises(FileExistsError):
            audit(self.run, self.manifest, output)

    def test_cropped_rotated_pdf_uses_crop_unrotated_frame(self):
        pdf_data = make_text_pdf(["INVOICE DEMONSTRATION ABCDEFG 123456789"], pages=2)
        stream = io.BytesIO()
        with pdfium.PdfDocument(pdf_data) as pdf:
            with closing(pdf[0]) as page:
                page.set_cropbox(20, 20, 620, 800)
                page.set_rotation(90)
            pdf.save(stream)
        self.prepare(stream.getvalue(), ".pdf")
        report = audit(self.run, self.manifest, self.root / "audit")
        self.assertEqual(report["audited_pages"], 4)
        page = report["pages"][0]
        self.assertEqual(page["coordinate_system"], "normalized_crop_unrotated_top_left")
        self.assertEqual(page["intrinsic_rotation"], 90)
        self.assertEqual(page["canonical_rotation"], 0)
        self.assertEqual(page["page_width_pt"], 600)
        self.assertEqual(page["effective_crop_bbox_pdf_points"], [20, 20, 620, 800])
        self.assertEqual(page["width_px"], 1667)

    def test_metadata_wrong_frame_rejected_even_with_matching_hash(self):
        self.prepare(self.jpeg(), ".jpg")
        self.update_metadata(lambda metadata: metadata["pages"][0].update(
            coordinate_system="normalized_crop_unrotated_top_left"))
        with self.assertRaisesRegex(ValueError, "coordinate frame"):
            audit(self.run, self.manifest, self.root / "audit")

    def test_metadata_page_loss_is_rejected(self):
        self.prepare(self.jpeg(), ".jpg")
        self.update_metadata(lambda metadata: metadata.update(pages=[]))
        with self.assertRaisesRegex(ValueError, "page counts"):
            audit(self.run, self.manifest, self.root / "audit")

    def test_changed_source_is_rejected(self):
        self.prepare(self.jpeg(), ".jpg")
        (self.root / "source.jpg").write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "source path/hash"):
            audit(self.run, self.manifest, self.root / "audit")

    def test_missing_success_handoff_rejected(self):
        self.prepare(self.jpeg(), ".jpg")
        path = self.run / "handoff.json"
        handoff = json.loads(path.read_text())
        handoff["samples"].pop()
        write(path, handoff)
        with self.assertRaisesRegex(ValueError, "coverage"):
            audit(self.run, self.manifest, self.root / "audit")

    def test_reference_only_manifest_change_rejected_before_output(self):
        self.prepare(self.jpeg(), ".jpg")
        manifest = json.loads(self.manifest.read_text())
        manifest["samples"][0]["reference"] = "A different source transcript"
        write(self.manifest, manifest)
        with self.assertRaisesRegex(ValueError, "manifest hash"):
            audit(self.run, self.manifest, self.root / "audit")
        self.assertFalse((self.root / "audit").exists())

    def test_legacy_handoff_is_explicitly_unbound(self):
        self.prepare(self.jpeg(), ".jpg")
        path = self.run / "handoff.json"
        handoff = json.loads(path.read_text())
        del handoff["manifest_sha256"]
        write(path, handoff)
        report = audit(self.run, self.manifest, self.root / "audit")
        self.assertEqual(report["manifest_binding"], "legacy_unbound_manifest")

    def test_failure_stays_in_cohort(self):
        self.prepare(self.jpeg(), ".jpg")
        path = self.run / "handoff.json"
        handoff = json.loads(path.read_text())
        handoff["samples"].pop()
        write(path, handoff)
        path = self.run / "comparison.json"
        comparison = json.loads(path.read_text())
        comparison["samples"][0].update(route_aware_status="failed", route_aware_error="OCR_FAILED")
        write(path, comparison)
        report = audit(self.run, self.manifest, self.root / "audit")
        self.assertEqual(report["expected_runs"], 2)
        self.assertEqual(report["audited_runs"], 1)
        self.assertEqual(report["failed_runs"], [{"id": "sample", "mode": "route_aware",
                                                 "status": "failed", "error": "OCR_FAILED"}])


if __name__ == "__main__":
    unittest.main()
