> **LEGACY v1 NOTICE (19/09/2026):** This directory belongs to the former five-field benchmark plan. Do not treat these artifacts as the v2 dataset strategy or final test set. See `docs/dataset-strategy.md` and `docs/migration-status.md`.

# Field-aware OCR evaluation input

`manifest.json` is the integration boundary between OCR evaluation and
KIE/Data-owned semantic ground truth. OCR must not populate semantic field
labels by copying its own predictions.

Each manifest record has this shape:

```json
{
  "test_id": "R001",
  "selection_stratum": "standard_mixed_layout",
  "annotation_path": "../annotations/R001.json",
  "real_ocr_path": "../../results/ocr_outputs/R001.json",
  "oracle_ocr_path": "../verified_ocr/R001.json",
  "oracle_qa_state": "VERIFIED",
  "oracle_provenance": "dual-reviewed block transcription batch oracle-v1"
}
```

`annotation_path` must validate against
`schemas/annotation-record.schema.json` and link to the exact real OCR receipt
and run IDs. `oracle_ocr_path` is optional until Data/KIE provides verified
canonical block evidence. When present, it must resolve to a different artifact
and a different `ocr_run_id` from the real OCR result, while retaining the same
`receipt_id`. The record must also set `oracle_qa_state` to `VERIFIED` and
provide non-empty `oracle_provenance` describing the review or adjudication
evidence. A canonical OCR JSON alone is not sufficient to count as Oracle
evidence. Paths are resolved relative to the manifest.

The committed manifest deliberately has no records because all current
transcriptions are pending independent QA and no five-field gold set has been
provided. This is a tracked dependency, not an empty-success result.

Generate the report with:

```bash
python scripts/evaluate_field_aware.py
```

Synthetic fixtures are accepted only when the caller explicitly enables
`allow_examples`; they cannot silently enter the benchmark report.
