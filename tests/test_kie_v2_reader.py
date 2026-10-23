"""Real PDFium Reader on a generated PDF; no OCR engine doubles or QA claims."""

import copy
import io
import unittest
from uuid import UUID

from ai.kie.v2 import extract_with_grouping
from ai.kie.v2.config import GROUPING_CONFIGURATIONS, HEADER_FIELDS, LINE_FIELDS
from ai.kie.v2.evaluation import metrics, validate_gold
from tests.kie_v2_fixtures import KIE_RUN, OCR_RUN, RECEIPT


def reader_case():
    from reportlab.pdfgen.canvas import Canvas
    from ai.document_reader import DocumentReader, ReaderConfig

    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
    canvas.setFont("Helvetica", 10)
    canvas.drawString(40, 740, "SYNTHETIC SOFTWARE TEST - NO FINANCIAL VALUE")
    canvas.drawString(40, 710, "Currency: VND")
    xs = [40, 220, 300, 390, 500]
    for x, label in zip(
        xs, ("Description", "Unit", "Quantity", "Unit price", "Amount")
    ):
        canvas.drawString(x, 650, label)
    values = [
        ("Service A", "box", "2", "50000", "100000"),
        ("Service B", "pack", "3", "20000", "60000"),
    ]
    for y, row in zip((620, 570), values):
        for x, value in zip(xs, row):
            canvas.drawString(x, y, value)
    canvas.drawString(40, 605, "continued")
    canvas.save()
    pdf = stream.getvalue()
    reader = DocumentReader(config=ReaderConfig(orientation="none"))
    evidence, audit = reader.process_with_metadata(
        pdf,
        content_type="application/pdf",
        receipt_id=UUID(RECEIPT),
        ocr_run_id=UUID(OCR_RUN),
    )
    blocks = evidence["pages"][0]["evidence"]["blocks"]

    def cell(value, printed):
        # Test-only alignment from independent printed literals to actual Reader
        # blocks, BEFORE calling either KIE variant. Never prediction-derived IDs.
        matches = [[b for b in blocks if b["text"] == token] for token in printed]
        if any(len(found) != 1 for found in matches):
            raise AssertionError(f"Reader tokens cannot be aligned uniquely: {printed}")
        return {
            "annotation_status": "PRESENT",
            "normalized_value": value,
            "raw_value": " ".join(printed),
            "source_block_ids": [found[0]["block_id"] for found in matches],
        }

    fields = {
        f: {
            "annotation_status": "UNKNOWN",
            "normalized_value": None,
            "raw_value": None,
            "source_block_ids": [],
        }
        for f in HEADER_FIELDS
    }
    fields["currency"] = cell("VND", ["Currency: VND"])
    expected = [
        ["Service A continued", "box", 2, 50000, 100000],
        ["Service B", "pack", 3, 20000, 60000],
    ]
    rows = []
    for i, (printed, normalized) in enumerate(zip(values, expected)):
        row = {"line_id": f"independent-source-row-{i}"}
        for f, text, value in zip(LINE_FIELDS, printed, normalized):
            row[f] = cell(
                value, [text, "continued"] if i == 0 and f == "description" else [text]
            )
        rows.append(row)
    gold = {
        "annotation_schema_version": "2.0",
        "receipt_id": RECEIPT,
        "dataset_family": "synthetic-reader-unit",
        "dataset_snapshot": "1",
        "sample_id": "generated-text-pdf",
        "synthetic": True,
        "split": "validation",
        "mapping_version": "test-only-manual-values-1",
        "fields": fields,
        "line_items": rows,
    }
    return pdf, evidence, audit, gold


class ReaderGroupingTests(unittest.TestCase):
    def test_real_reader_output_alignment_and_both_groupings(self):
        _, evidence, _, gold = reader_case()
        before = copy.deepcopy(evidence)
        self.assertEqual(
            evidence["pages"][0]["evidence"]["engine"]["name"], "pdfium-text"
        )
        validate_gold(gold, evidence, gold)
        for grouping in GROUPING_CONFIGURATIONS:
            result = extract_with_grouping(
                evidence, kie_run_id=KIE_RUN, grouping=grouping
            )
            measured = metrics([(result, gold)])
            self.assertEqual(measured["lines"]["detection_f1"], 1)
            self.assertEqual(measured["lines"]["complete_line_accuracy"], 1)
            self.assertEqual(measured["header_micro_accuracy"], 1)
            self.assertFalse(
                any(
                    "independent-source-row" in i
                    for r in result["line_items"]
                    for i in r["source_block_ids"]
                )
            )
        self.assertEqual(evidence, before)


if __name__ == "__main__":
    unittest.main()
