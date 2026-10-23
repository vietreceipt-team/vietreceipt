## Summary

Addresses the feedback on #60 and continues #47 with a self-contained TV4 development/validation handoff.

- Adds `data/handoffs/tv4-dev-v1.zip`: 80 predeclared input files from 20 synthetic source invoices (60 train / 20 validation), including text PDFs, PNGs, scanned PDFs and blur PNGs.
- Preserves original source gold, 13 header fields and 5 cells per row; adds source cell/row regions, actual reader evidence, hashes, run IDs, complete logs/runtime/model provenance and a gallery of every input.
- Proposes links only to actual spatial reader blocks. OCR text disagreement is reported without replacing source values or relabeling missing content as NOT_PRESENT.
- Adds pending review templates, integrity/leakage checks and an explicit coordination checklist.
- Expands public-data audits: 982 Vietnamese records (969 mapped), 200 CORD records (176 mapped), and 626 SROIE-curated train records (625 mapped). Native labels, raw text, masks, rejected-record reports and pinned snapshots are retained.

## Validation

- 108 dataset/KIE/reader tests passed; Ruff passed.
- Existing shared contract tests passed with requirements-contracts.txt versions. Windows invocation uses `python -X utf8`.
- All 80 declared inputs returned actual schema-valid reader evidence.
- Handoff integrity passed: artifact hashes, source-value/status preservation, real block IDs, source regions, complete counts and no base/template/content split leakage.
- All mapped public samples passed automated schema/image/hash/mask checks.

## Review gates and remaining coordination

The package is **PENDING_REVIEW**, not VERIFIED gold or a final accuracy benchmark. All 80 inputs have spatial alignment candidates; the OCR-disagreement report and pending templates require actual owner review. No final test or oracle is included.

See `docs/data/coordination-required.md` for owners and exact missing inputs:
- TV4 must publish the grouping evaluator/protocol contract shown in the request (`--output`, `tests.test_kie_v2_grouping`, experiment schema).
- TV1/TV2/TV4/TV5 must confirm status/denominator/failure rules and the 13-header + line-item scope (tax excluded).
- Reviewers must approve actual source-to-block links; TV3/TV4 confirm reader geometry/version.
- The lead must approve the named SROIE curated source or request the organizer archive.
- An independent mock author/reviewer and final configuration/test freeze remain required.

Related: #47, #59, #60, #65. **Do not close #47.** This branch replaces the overlapping draft #60; do not merge both implementations.
