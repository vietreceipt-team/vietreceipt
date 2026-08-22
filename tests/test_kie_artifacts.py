from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from ai.kie.artifacts import (
    run_and_write_kie,
    write_kie_artifact,
)
from ai.kie.contract import validate_kie_result


RECEIPT_ID = "11111111-1111-4111-8111-111111111111"
OCR_RUN_ID = "22222222-2222-4222-8222-222222222222"
FIRST_KIE_RUN_ID = UUID(
    "33333333-3333-4333-8333-333333333333"
)
SECOND_KIE_RUN_ID = UUID(
    "44444444-4444-4444-8444-444444444444"
)


def make_empty_ocr() -> dict:
    return {
        "schema_version": "1.3",
        "receipt_id": RECEIPT_ID,
        "ocr_run_id": OCR_RUN_ID,
        "engine": {
            "name": "test-ocr",
            "version": "0.1.0",
        },
        "image": {
            "width_px": 1000,
            "height_px": 1600,
        },
        "blocks": [],
        "average_confidence": 0.0,
        "duration_ms": 100,
    }


class KIEArtifactTests(unittest.TestCase):

    def test_reprocess_creates_distinct_immutable_artifacts(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_root = (
                Path(temporary_directory)
                / "kie_outputs"
            )

            first_result, first_path = run_and_write_kie(
                make_empty_ocr(),
                kie_run_id=FIRST_KIE_RUN_ID,
                output_root=output_root,
            )
            first_bytes = first_path.read_bytes()

            second_result, second_path = run_and_write_kie(
                make_empty_ocr(),
                kie_run_id=SECOND_KIE_RUN_ID,
                output_root=output_root,
            )

            self.assertNotEqual(first_path, second_path)
            self.assertTrue(first_path.is_file())
            self.assertTrue(second_path.is_file())
            self.assertEqual(first_path.read_bytes(), first_bytes)

            self.assertEqual(
                first_path,
                output_root
                / RECEIPT_ID
                / f"{FIRST_KIE_RUN_ID}.json",
            )
            self.assertEqual(
                second_path,
                output_root
                / RECEIPT_ID
                / f"{SECOND_KIE_RUN_ID}.json",
            )

            first_document = json.loads(
                first_path.read_text(encoding="utf-8")
            )
            second_document = json.loads(
                second_path.read_text(encoding="utf-8")
            )

            validate_kie_result(first_document)
            validate_kie_result(second_document)
            self.assertEqual(first_document, first_result)
            self.assertEqual(second_document, second_result)
            self.assertEqual(
                first_document["source_ocr_run_id"],
                second_document["source_ocr_run_id"],
            )
            self.assertNotEqual(
                first_document["kie_run_id"],
                second_document["kie_run_id"],
            )

    def test_existing_kie_run_artifact_is_never_overwritten(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_root = (
                Path(temporary_directory)
                / "kie_outputs"
            )

            result, artifact_path = run_and_write_kie(
                make_empty_ocr(),
                kie_run_id=FIRST_KIE_RUN_ID,
                output_root=output_root,
            )
            original_bytes = artifact_path.read_bytes()

            with self.assertRaises(FileExistsError):
                write_kie_artifact(
                    result,
                    output_root=output_root,
                )

            self.assertEqual(
                artifact_path.read_bytes(),
                original_bytes,
            )


if __name__ == "__main__":
    unittest.main()
