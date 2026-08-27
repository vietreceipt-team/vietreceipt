from __future__ import annotations

import copy
import unittest

from ai.kie.gold_workflow import (
    ADJUDICATION_SCHEMA_PATH,
    ANNOTATION_SCHEMA_PATH,
    ORACLE_QA_SCHEMA_PATH,
    annotation_draft,
    disagreement_fields,
    oracle_draft,
    pending_manifest,
    schema_errors,
    semantic_label,
)
from ai.ocr.contract import validate_ocr_result


REAL_OCR = {
    "schema_version": "1.3",
    "receipt_id": "11111111-1111-4111-8111-111111111111",
    "ocr_run_id": "22222222-2222-4222-8222-222222222222",
    "engine": {"name": "synthetic-real", "version": "1.0"},
    "image": {"width_px": 100, "height_px": 200},
    "blocks": [
        {
            "block_id": "block_0",
            "text": "SYNTHETIC STORE",
            "confidence": 0.8,
            "polygon": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.9, "y": 0.1},
                {"x": 0.9, "y": 0.2},
                {"x": 0.1, "y": 0.2},
            ],
            "reading_order": 0,
        }
    ],
    "average_confidence": 0.8,
    "duration_ms": 1,
}


def complete_unknown_annotation(slot: str) -> dict:
    annotation = annotation_draft("R001", REAL_OCR, slot=slot)
    annotation["data_provenance"] = "Synthetic unit-test human annotation."
    annotation["annotator_id"] = f"synthetic-{slot}"
    annotation["annotated_at"] = "2026-08-26T00:00:00Z"
    for field in annotation["fields"].values():
        field["annotation_status"] = "UNKNOWN"
        field["annotator_note"] = "Synthetic unit-test unknown field."
    return annotation


class W3GoldWorkflowTests(unittest.TestCase):
    def test_pending_manifest_tracks_exactly_r001_through_r040(self) -> None:
        manifest = pending_manifest()
        self.assertEqual(
            [record["test_id"] for record in manifest["records"]],
            [f"R{index:03d}" for index in range(1, 41)],
        )
        self.assertNotEqual(manifest["annotation_qa_state"], "VERIFIED")
        self.assertTrue(
            all(
                record["oracle_qa_state"] != "VERIFIED"
                for record in manifest["records"]
            )
        )

    def test_annotation_draft_is_incomplete_instead_of_fabricated(self) -> None:
        draft = annotation_draft("R001", REAL_OCR, slot="annotator-a")
        errors = schema_errors(draft, ANNOTATION_SCHEMA_PATH)
        self.assertTrue(errors)
        self.assertIsNone(
            draft["fields"]["total_amount"]["annotation_status"]
        )

    def test_completed_annotation_form_validates(self) -> None:
        annotation = complete_unknown_annotation("annotator-a")
        self.assertEqual(
            schema_errors(annotation, ANNOTATION_SCHEMA_PATH),
            [],
        )

    def test_oracle_draft_has_distinct_run_and_canonical_shape(self) -> None:
        draft = oracle_draft("R001", REAL_OCR)
        validate_ocr_result(draft)
        self.assertEqual(draft["receipt_id"], REAL_OCR["receipt_id"])
        self.assertNotEqual(draft["ocr_run_id"], REAL_OCR["ocr_run_id"])
        self.assertEqual(draft["blocks"], REAL_OCR["blocks"])
        self.assertIn("draft", draft["engine"]["name"])

    def test_disagreement_compares_status_value_candidates_and_evidence(self) -> None:
        annotation_a = complete_unknown_annotation("annotator-a")
        annotation_b = complete_unknown_annotation("annotator-b")
        self.assertEqual(disagreement_fields(annotation_a, annotation_b), [])

        annotation_b = copy.deepcopy(annotation_b)
        annotation_b["fields"]["invoice_id"] = {
            "field_name": "invoice_id",
            "annotation_status": "NOT_PRESENT",
            "transcribed_value": None,
            "normalized_value": None,
            "source_block_ids": [],
            "candidate_values": [],
            "annotator_note": None,
        }
        self.assertEqual(
            disagreement_fields(annotation_a, annotation_b),
            ["invoice_id"],
        )
        self.assertEqual(
            set(semantic_label(annotation_a["fields"]["invoice_id"])),
            {
                "annotation_status",
                "normalized_value",
                "candidate_values",
                "source_block_ids",
            },
        )

    def test_new_human_audit_schemas_are_valid_json_schemas(self) -> None:
        # Constructing validators performs Draft 2020-12 schema validation.
        self.assertIsInstance(schema_errors({}, ADJUDICATION_SCHEMA_PATH), list)
        self.assertIsInstance(schema_errors({}, ORACLE_QA_SCHEMA_PATH), list)


if __name__ == "__main__":
    unittest.main()
