"""TV2 intake integrity and saved Reader regressions, not benchmark gold QA."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ai.kie.v2 import extract_invoice, extract_with_grouping
from ai.kie.v2.config import INTERVAL_GROUPING, LINE_FIELDS, GROUPING_CONFIGURATIONS
from ai.kie.v2.evaluation import ROOT, VERSION
from ai.kie.v2.evidence import flatten
from ai.kie.v2.extraction import extract_tables, table_regions
from ai.kie.v2.grouping import EXPERIMENT_LINE_LABELS, EXPERIMENT_LINE_STOP
from jsonschema import Draft202012Validator
from scripts.inspect_invoice_handoff import inspect
from tests.kie_v2_fixtures import KIE_RUN, invoice
from tests.test_kie_v2_evaluation import gold_fixture


class SavedReaderTests(unittest.TestCase):
    def test_real_saved_reader_text_and_ocr_keep_source_provenance(self):
        directory = Path(__file__).parent / "fixtures/kie49/reader-tv2"
        metadata = json.loads((directory / "provenance.json").read_text())
        for kind, refs in metadata["files"].items():
            with self.subTest(kind=kind):
                data = (directory / (kind + ".json")).read_bytes()
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(), refs["evidence_sha256"]
                )
                evidence = json.loads(data)
                original = copy.deepcopy(evidence)
                self.assertEqual(
                    extract_invoice(evidence, kie_run_id=KIE_RUN)["line_items"], []
                )
                result = extract_with_grouping(
                    evidence, kie_run_id=KIE_RUN, grouping=INTERVAL_GROUPING
                )
                self.assertEqual(evidence, original)
                self.assertEqual(
                    result,
                    extract_with_grouping(
                        evidence, kie_run_id=KIE_RUN, grouping=INTERVAL_GROUPING
                    ),
                )
                blocks = {b.block_id: b.text for b in flatten(evidence)}
                for row in result["line_items"]:
                    self.assertTrue(set(row["source_block_ids"]) <= set(blocks))
                if kind == "text_pdf":
                    alias_only, _ = table_regions(
                        flatten(evidence),
                        line_labels=EXPERIMENT_LINE_LABELS,
                        line_stop_pattern=EXPERIMENT_LINE_STOP,
                    )
                    self.assertEqual(len(extract_tables(alias_only, "VND")[0]), 3)
                    # Transcribed from source-preview.png, not from model output.
                    self.assertEqual(
                        [
                            [r[f]["normalized_value"] for f in LINE_FIELDS]
                            for r in result["line_items"]
                        ],
                        [
                            ["Bìa hồ sơ", "Cái", 6, 7000, 42000],
                            ["Bút bi xanh", "Cây", 4, 5000, 20000],
                            ["Bút bi xanh", "Cây", 5, 5000, 25000],
                            ["Sổ tay văn phòng", "Quyển", 4, 18000, 72000],
                            ["Mực máy in", "Hộp", 5, 145000, 725000],
                        ],
                    )
                elif kind in {"clean_png", "blur_png"}:
                    self.assertEqual(len(result["line_items"]), 5)
                    # Keep OCR misspellings; neither normalization nor grouping
                    # may manufacture the accents printed in source gold.
                    for row in result["line_items"]:
                        self.assertEqual(
                            row["description"]["raw_text"],
                            blocks[row["description"]["source_block_ids"][0]],
                        )
                else:
                    self.assertEqual(
                        result["line_items"], []
                    )  # Unrepaired OCR header limitation.


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        evidence, gold = invoice(), gold_fixture()
        evidence_id = evidence["receipt_id"]
        source_gold = copy.deepcopy(gold)
        for c in list(source_gold["fields"].values()) + [
            source_gold["line_items"][0][f] for f in LINE_FIELDS
        ]:
            c["source_block_ids"] = []
        self.record = {
            "record_id": gold["sample_id"],
            "base_document_id": "base-1",
            "template_id": "template-1",
            "split": "validation",
            "qa_status": "PENDING_REVIEW",
            "final_eligible": False,
            "original_sample_id": gold["sample_id"],
            "source_receipt_id": evidence_id,
            "receipt_id": evidence_id,
            "reader_run_id": evidence["ocr_run_id"],
            "reader_status": "SUCCESS",
            "source_type": "text_pdf",
            "augmentation_type": "clean",
            "source": self.artifact("source.bin", b"synthetic source bytes"),
            "source_gold": self.artifact("source-gold.json", source_gold),
            "gold": self.artifact("gold.json", gold),
            "evidence": self.artifact("evidence.json", evidence),
            "source_regions": self.artifact("regions.json", []),
            "source_row_regions": self.artifact(
                "rows.json",
                [
                    {
                        "line_id": "gold-A",
                        "page_index": 0,
                        "bounds": [0.05, 0.38, 0.97, 0.394],
                    }
                ],
            ),
            "reader_log": self.artifact("reader.log", b"synthetic log"),
            "reader_metadata": self.artifact(
                "reader.json", {"scope": "synthetic fixture"}
            ),
        }
        self.manifests = {}
        for split in ("train", "validation"):
            self.manifests[split] = {
                k: gold[k] for k in ("dataset_family", "dataset_snapshot", "synthetic")
            }
            self.manifests[split].update(
                schema_version="tv2-tv4-handoff-candidate-0.1",
                split=split,
                qa_status="PENDING_REVIEW",
                frozen=True,
                sample_count=int(split == "validation"),
                records=[self.record] if split == "validation" else [],
            )

    def artifact(self, name, value):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        (self.root / name).write_bytes(data)
        return {"path": name, "sha256": hashlib.sha256(data).hexdigest()}

    def run_inspection(self):
        for split, manifest in self.manifests.items():
            (self.root / (split + "-manifest.json")).write_text(json.dumps(manifest))
        return inspect(self.root, self.root / "output", "synthetic-test-only")

    def test_pending_package_runs_without_accuracy_or_qa_mutation(self):
        report = self.run_inspection()
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["kie_paired_success"], 1)
        self.assertIsNone(report["metrics"])
        self.assertFalse(report["grants_verified"])
        gate = json.loads(
            (self.root / "output/validation-formal-gate.json").read_text()
        )
        self.assertEqual(gate["coverage"]["required"], 1)
        self.assertEqual(gate["evaluated"], 0)
        self.assertIsNone(gate["metrics"])

    def test_hash_failure_prevents_all_extraction(self):
        (self.root / "evidence.json").write_text("{}")
        report = self.run_inspection()
        self.assertEqual(report["kie_paired_success"], 0)
        self.assertTrue(report["failures"])
        self.assertFalse((self.root / "output/predictions").exists())

    def test_candidate_value_mutation_not_accepted(self):
        gold = json.loads((self.root / "gold.json").read_text())
        gold["fields"]["invoice_number"]["normalized_value"] = "changed"
        self.record["gold"] = self.artifact("gold.json", gold)
        report = self.run_inspection()
        self.assertEqual(report["kie_paired_success"], 0)
        self.assertIn("changed source values", str(report["failures"]))

    def test_reader_failure_stays_in_cohort(self):
        self.record["reader_status"] = "FAILED"
        report = self.run_inspection()
        self.assertEqual(report["required"], 1)
        self.assertEqual(report["reader_failed"], 1)
        self.assertEqual(report["kie_paired_success"], 0)

    def test_final_input_rejected(self):
        self.record["final_eligible"] = True
        self.assertEqual(self.run_inspection()["kie_paired_success"], 0)

    def test_experiment_schema_matches_runtime(self):
        schema = json.loads(
            (ROOT / "schemas/invoice-kie-experiment.v1.schema.json").read_text()
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(
            {
                "protocol": "grouping-ab-1.0",
                "evaluator_version": VERSION,
                "configurations": GROUPING_CONFIGURATIONS,
            }
        )
