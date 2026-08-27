# W3 Oracle OCR workspace

Every file in `drafts/` is a PENDING bootstrap copied from the corresponding
Real OCR artifact with a distinct deterministic `ocr_run_id`. A canonical JSON
shape does not make it Oracle evidence. Its text, blocks, order, geometry and
provenance require human correction and independent review.

Every file in `qa/` is intentionally incomplete. It must fail the Oracle QA
schema until a named preparer and a different reviewer record the final
artifact hash, findings, timestamps and explicit `VERIFIED` decision.

The evaluation manifest remains PENDING and metrics remain null until all 40
human QA records and all five-field annotations pass the W3 gate.
