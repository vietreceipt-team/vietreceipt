"""Algorithm, source provenance and V2 regression checks; no corpus QA claims."""

import copy
import hashlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from ai.kie.v2 import extract_invoice
from ai.kie.v2.config import BASELINE_GROUPING, LINE_FIELDS
from ai.kie.v2.contract import validate_result
from ai.kie.v2.evaluation import metrics
from ai.kie.v2.evidence import flatten
from ai.kie.v2.extraction import extract_tables, table_regions
from ai.table.structure import extract_table_structure, structure_rows
from tests.kie_table_structure_fixtures import cases
from tests.kie_v2_fixtures import KIE_RUN
from tests.kie_v2_fixtures import OCR_RUN, RECEIPT


def rows(source):
    return structure_rows(flatten(source), currency="VND")


class TableStructureTests(unittest.TestCase):
    def test_region_contract_and_input_immutability_all_cases(self):
        for name, case in cases().items():
            with self.subTest(name=name):
                source = case["evidence"]
                original = copy.deepcopy(source)
                baseline = extract_invoice(source, kie_run_id=KIE_RUN)
                variant = copy.deepcopy(baseline)
                variant["line_items"] = rows(source)
                validate_result(variant, source, kie_run_id=KIE_RUN)
                self.assertEqual(source, original)
                self.assertEqual(variant["line_items"], rows(source))
                self.assertEqual(baseline, extract_invoice(source, kie_run_id=KIE_RUN))

    def test_baseline_strategy_is_exact_existing_algorithm(self):
        for case in cases().values():
            blocks = flatten(case["evidence"])
            regions, _ = table_regions(blocks)
            expected = extract_tables([r for r in regions if r[0] == "line"], "VND")[0]
            self.assertEqual(
                expected,
                structure_rows(blocks, currency="VND", strategy=BASELINE_GROUPING),
            )

    def test_narrow_numbers_and_staggered_columns(self):
        for name in ("borderless", "staggered-quantity"):
            actual = rows(cases()[name]["evidence"])
            self.assertEqual(len(actual), 2)
            self.assertEqual(
                [actual[0][f]["normalized_value"] for f in LINE_FIELDS],
                ["Service A", "box", 2, 50000, 100000],
            )

    def test_description_fragments_keep_exact_raw_source(self):
        for name, expected in (
            ("wrapped-description", "Service A continued"),
            ("split-description", "Service A"),
        ):
            row = rows(cases()[name]["evidence"])[0]
            self.assertEqual(row["description"]["normalized_value"], expected)
            self.assertEqual(len(row["description"]["source_block_ids"]), 2)
        self.assertIn(
            "AMBIGUOUS_FORMAT",
            rows(cases()["wrapped-description"]["evidence"])[0]["review_reasons"],
        )

    def test_split_and_merged_numbers_are_never_repaired(self):
        for name in ("split-number", "merged-numbers"):
            row = rows(cases()[name]["evidence"])[0]
            self.assertEqual(row["unit_price"]["value_status"], "AMBIGUOUS")
            self.assertIsNone(row["unit_price"]["normalized_value"])
            self.assertTrue(row["machine_needs_review"])
        merged = rows(cases()["merged-numbers"]["evidence"])[0]
        self.assertEqual(
            merged["unit_price"]["source_block_ids"],
            merged["amount"]["source_block_ids"],
        )
        self.assertEqual(merged["amount"]["raw_text"], "50000 100000")
        self.assertIsNone(merged["amount"]["normalized_value"])

    def test_missing_unit_column_and_missing_cell_remain_distinct(self):
        for name, status in (
            ("missing-unit-column", "NOT_PRESENT"),
            ("missing-unit-cell", "UNKNOWN"),
        ):
            self.assertEqual(
                rows(cases()[name]["evidence"])[0]["unit"]["value_status"], status
            )

    def test_repeated_headers_and_page_boundaries(self):
        for name in ("repeated-header", "multiple-pages"):
            actual = rows(cases()[name]["evidence"])
            self.assertEqual(len(actual), 2)
            self.assertEqual(len({row["line_id"] for row in actual}), 2)
            self.assertTrue(
                all(
                    "header" not in row["description"]["raw_text"].lower()
                    for row in actual
                )
            )
        multiple = rows(cases()["multiple-pages"]["evidence"])
        self.assertTrue(
            all(i.startswith("p1_") for i in multiple[1]["source_block_ids"])
        )

    def test_vertically_merged_unit_is_ambiguous_in_both_rows(self):
        source = cases()["borderless"]["evidence"]
        # A single OCR box now spans the two original source rows.
        source["blocks"] = [b for b in source["blocks"] if b["block_id"] != "p0_b11"]
        for index, block in enumerate(source["blocks"]):
            block["reading_order"] = index
        unit = source["blocks"][6]
        for p in unit["polygon"][2:]:
            p["y"] = 0.38
        actual = rows(source)
        self.assertEqual(len(actual), 2)
        for row in actual:
            self.assertIn("p0_b6", row["unit"]["source_block_ids"])
            self.assertEqual(row["unit"]["value_status"], "AMBIGUOUS")
            self.assertIsNone(row["unit"]["normalized_value"])

    def test_tall_description_does_not_merge_two_numeric_rows(self):
        source = cases()["borderless"]["evidence"]
        source["blocks"] = [b for b in source["blocks"] if b["block_id"] != "p0_b10"]
        for index, block in enumerate(source["blocks"]):
            block["reading_order"] = index
            if block["block_id"] == "p0_b5":
                for p in block["polygon"][2:]:
                    p["y"] = 0.38
        actual = rows(source)
        self.assertEqual(len(actual), 2)
        self.assertEqual(
            [row["quantity"]["normalized_value"] for row in actual], [2, 3]
        )
        for row in actual:
            self.assertEqual(row["description"]["value_status"], "AMBIGUOUS")
            self.assertEqual(row["description"]["source_block_ids"], ["p0_b5"])

    def test_unsupported_header_and_partial_item_are_not_claimed_fixed(self):
        source = cases()["unheaded"]["evidence"]
        result = extract_table_structure(source, page_index=0, bbox=(0, 0, 1, 1))
        self.assertEqual(result["status"], "NO_ROWS_DETECTED")
        self.assertTrue(result["machine_needs_review"])
        self.assertEqual(len(result["unassigned_block_ids"]), 6)
        actual = rows(cases()["ambiguous-partial-next-item"]["evidence"])
        self.assertEqual(len(actual), 1)
        self.assertIn("AMBIGUOUS_FORMAT", actual[0]["description"]["review_reasons"])

    def test_invalid_regions_and_strategies_fail_explicitly(self):
        source = cases()["bordered"]["evidence"]
        for bbox in (
            (0, 0, float("nan"), 1),
            (0, 0, 2, 1),
            (0, 0, 0.15, 0.30),
            (False, 0, 1, 1),
        ):
            with self.assertRaises(ValueError):
                extract_table_structure(source, page_index=0, bbox=bbox)
        with self.assertRaises(ValueError):
            extract_table_structure(source, page_index=True, bbox=(0, 0, 1, 1))
        with self.assertRaises(ValueError):
            structure_rows(flatten(source), strategy="unknown")

    def test_ruling_images_and_provenance_are_actual_hashed_sources(self):
        base = Path(__file__).parent / "fixtures/table_structure"
        manifest = json.loads((base / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["split"], "development")
        self.assertEqual(manifest["qa_status"], "NOT_INDEPENDENTLY_REVIEWED")
        image_hashes = set()
        for item in manifest["records"]:
            for kind in ("image", "evidence", "expected"):
                blob = (base / item[kind]["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(blob).hexdigest(), item[kind]["sha256"])
                if kind == "image":
                    self.assertTrue(blob.startswith(b"\x89PNG\r\n\x1a\n"))
                    image_hashes.add(item[kind]["sha256"])
            source = json.loads(
                (base / item["evidence"]["path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(source, cases()[item["ruling"]]["evidence"])
            self.assertEqual(len(rows(source)), 2)
        self.assertEqual(len(image_hashes), 4)

    def test_existing_evaluator_counts_unresolved_and_failed_inputs(self):
        case = cases()["merged-numbers"]
        result = extract_invoice(case["evidence"], kie_run_id=KIE_RUN)
        result["line_items"] = rows(case["evidence"])
        report = metrics([(result, case["gold"]), (None, case["gold"])])
        self.assertEqual(report["lines"]["failed_documents"], 1)
        self.assertEqual(report["lines"]["gold_rows"], 4)
        self.assertLess(report["lines"]["complete_line_accuracy"], 1)
        self.assertEqual(report["header_coverage"]["scored"], 0)

    def test_runner_keeps_official_scores_null_and_failure_denominators(self):
        from scripts.evaluate_table_structure import compare

        report = compare(repeats=1)
        self.assertEqual(report["status"], "NOT_SCORED")
        self.assertIsNone(report["metrics"])
        self.assertTrue(
            all(v["synthetic_diagnostics"] is None for v in report["variants"].values())
        )
        with patch(
            "scripts.evaluate_table_structure.extract_table_structure",
            side_effect=ValueError("injected Table failure"),
        ):
            failed = compare(synthetic_diagnostics=True, repeats=1)
        for variant in failed["variants"].values():
            self.assertEqual(variant["failure_count"], 16)
            self.assertEqual(variant["synthetic_diagnostics"]["lines"]["gold_rows"], 27)
            self.assertEqual(
                variant["synthetic_diagnostics"]["lines"]["failed_documents"], 16
            )

    @unittest.skipUnless(
        all(
            importlib.util.find_spec(p) is not None for p in ("reportlab", "pypdfium2")
        ),
        "requires optional Reader test dependencies",
    )
    def test_actual_pdfium_reader_for_four_ruling_styles(self):
        from reportlab.pdfgen.canvas import Canvas
        from ai.document_reader import DocumentReader, ReaderConfig

        for ruling in ("bordered", "borderless", "horizontal", "vertical"):
            with self.subTest(ruling=ruling):
                stream = io.BytesIO()
                canvas = Canvas(stream, pagesize=(1000, 1400), invariant=1)
                xs, ys = [35, 365, 505, 660, 815, 980], [1135, 1070, 955, 835]
                if ruling in {"bordered", "horizontal"}:
                    for y in ys:
                        canvas.line(xs[0], y, xs[-1], y)
                if ruling in {"bordered", "vertical"}:
                    for x in xs:
                        canvas.line(x, ys[-1], x, ys[0])
                canvas.setFont("Helvetica", 14)
                source = cases()[ruling]["evidence"]
                for block in source["blocks"]:
                    point = block["polygon"][0]
                    canvas.drawString(
                        point["x"] * 1000, 1400 - point["y"] * 1400 - 14, block["text"]
                    )
                canvas.save()
                reader = DocumentReader(config=ReaderConfig(orientation="none"))
                actual = reader.process(
                    stream.getvalue(),
                    content_type="application/pdf",
                    receipt_id=UUID(RECEIPT),
                    ocr_run_id=UUID(OCR_RUN),
                )
                original = copy.deepcopy(actual)
                result = extract_table_structure(
                    actual, page_index=0, bbox=(0, 0.18, 1, 0.60), currency="VND"
                )
                self.assertEqual(actual, original)
                self.assertEqual(len(result["line_items"]), 2)
                self.assertEqual(
                    [
                        result["line_items"][0][f]["normalized_value"]
                        for f in LINE_FIELDS
                    ],
                    ["Service A", "box", 2, 50000, 100000],
                )


if __name__ == "__main__":
    unittest.main()
