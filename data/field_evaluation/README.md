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
  "oracle_ocr_path": "../verified_ocr/R001.json"
}
```

`annotation_path` must validate against
`schemas/annotation-record.schema.json` and link to the exact real OCR receipt
and run IDs. `oracle_ocr_path` is optional until Data/KIE provides verified
canonical block evidence; when present, it must be an OCRResult v1.3 for the
same receipt. Paths are resolved relative to the manifest.

The committed manifest deliberately has no records because all current
transcriptions are pending independent QA and no five-field gold set has been
provided. This is a tracked dependency, not an empty-success result.

Generate the report with:

```bash
python scripts/evaluate_field_aware.py
```

Synthetic fixtures are accepted only when the caller explicitly enables
`allow_examples`; they cannot silently enter the benchmark report.
