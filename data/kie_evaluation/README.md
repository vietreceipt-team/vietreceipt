# KIE field-level evaluation manifest

`manifest.json` is the QA gate for the frozen 40-receipt KIE split.
It intentionally contains no records until independent five-field
annotation, adjudication and Oracle OCR verification are complete.

Official evaluation must not use OCR transcription files from
`data/ground_truth/` as semantic KIE labels.

Each verified manifest record has this shape:

```json
{
  "test_id": "R001",
  "annotation_path": "data/kie_annotations/final/R001.json",
  "real_ocr_path": "results/ocr_outputs/R001.json",
  "oracle_ocr_path": "data/kie_oracle_ocr/R001.json",
  "oracle_qa_state": "VERIFIED",
  "oracle_provenance": "non-empty description of how Oracle OCR was produced and reviewed"
}
```

Before metrics are computed, the evaluator requires:

- top-level `annotation_qa_state` equal to `VERIFIED`;
- non-empty `annotation_provenance`;
- exactly the test IDs in the frozen split;
- annotation records that validate against
  `schemas/annotation-record.schema.json` and have `example_only=false`;
- annotation `source_ocr_run_id` linked to the Real OCR artifact;
- Real and Oracle OCR artifacts for the same receipt but with different
  paths and different `ocr_run_id` values;
- `oracle_qa_state=VERIFIED` and non-empty Oracle provenance.

Run:

```bash
python scripts/evaluate_kie.py
```

Exit code `0` means evaluation completed. Exit code `2` means the report
was written with status `WAITING_FOR_VERIFIED_FIELD_ANNOTATIONS`; its
metrics remain `null`. Invalid or inconsistent artifacts raise an error
instead of being silently skipped.
