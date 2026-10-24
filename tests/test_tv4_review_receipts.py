"""Review receipts must not accept self-review, stale bytes or substituted references."""

import tempfile
import unittest
from pathlib import Path

from scripts.data.check_tv4_reviews import check
from scripts.data.common import dump, sha


class ReviewReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        dump(self.root / "artifact.json", {"fixture": True})
        ref = dict(path="artifact.json", sha256=sha(self.root / "artifact.json"))
        refs = {
            k: dict(ref)
            for k in (
                "source",
                "source_gold",
                "source_regions",
                "source_row_regions",
                "evidence",
                "gold",
            )
        }
        dump(
            self.root / "evaluation-intake.json",
            dict(
                review_records=[
                    dict(record_id="fixture", split="train", review_path="review.json")
                ]
            ),
        )
        dump(
            self.root / "evaluator-train-manifest.json",
            dict(records=[dict(record_id="fixture", **refs)]),
        )
        self.review = dict(
            record_id="fixture",
            reviewed_by="Fixture reviewer",
            annotation_author="Fixture author",
            reviewed_at="2026-10-24T10:00:00+07:00",
            artifact_hashes=refs,
            unresolved=[],
            source_label_changes=[],
        )
        for k in (
            "independent_reviewer_confirmed",
            "source_gold_approved",
            "source_regions_approved",
            "source_rows_approved",
            "block_alignment_approved",
        ):
            self.review[k] = True

    def run_check(self):
        dump(self.root / "review.json", self.review)
        return check(self.root)

    def test_complete_receipt_never_grants_verified(self):
        result = self.run_check()
        self.assertEqual(result["review_receipts_complete"], 1)
        self.assertFalse(result["grants_verified"])

    def test_self_review_rejected(self):
        self.review["reviewed_by"] = self.review["annotation_author"]
        self.assertEqual(self.run_check()["review_receipts_complete"], 0)

    def test_missing_approval_and_naive_date_rejected(self):
        self.review["source_regions_approved"] = False
        self.review["reviewed_at"] = "2026-10-24T10:00:00"
        self.assertEqual(self.run_check()["review_receipts_complete"], 0)

    def test_changed_bytes_rejected(self):
        dump(self.root / "artifact.json", {"changed": True})
        self.assertEqual(self.run_check()["review_receipts_complete"], 0)

    def test_substituted_valid_hash_rejected(self):
        dump(self.root / "other.json", {"other": True})
        self.review["artifact_hashes"]["source"] = dict(
            path="other.json", sha256=sha(self.root / "other.json")
        )
        self.assertEqual(self.run_check()["review_receipts_complete"], 0)

    def test_source_label_changes_require_owner(self):
        self.review["source_label_changes"] = ["fixture label correction"]
        self.assertEqual(self.run_check()["review_receipts_complete"], 0)


if __name__ == "__main__":
    unittest.main()
