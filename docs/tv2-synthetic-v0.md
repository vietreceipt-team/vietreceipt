# TV2 synthetic v0 and TV3 OCR handoff

This starter generator creates deterministic, fictional Vietnamese invoice-like documents and schema-v2 ground-truth JSON. It is a development dataset, not real invoices or evidence of real-world accuracy.

## Generate the initial dataset

From the repository root (Python 3.10+; standard library only):

```bash
python scripts/generate_synthetic_v0.py --out data/vietreceipt_synthetic_v0 --count 30
```

It creates:
- `documents/*.svg`: renderable invoice documents;
- `labels/*.json`: ground truth in the structure of `schemas/invoice-annotation.v2.schema.json`;
- `manifest.csv`: sample ID, paths, layout family, split, and provenance.

The output folder is generated locally and should be reviewed before large data artifacts are committed. SVGs can be opened in a browser or converted to PNG/PDF for the OCR pipeline.

## Split policy

The generator assigns one layout family per split: `layout_a=train`, `layout_b=validation`, `layout_c=test`. This intentionally avoids placing variants from the same layout family across splits, but three layouts are only a smoke-test dataset, not a statistically strong benchmark. For the final evaluation, create a separate independent mock set with layouts not produced by this generator and keep it untouched until the code/configuration is frozen.

## TV3 handoff

Send TV3 a small sample first. Keep the original SVG/converted image or PDF and the matching JSON label together. Record:
- `sample_id` and document path;
- input route (image, text PDF, scanned PDF);
- quality condition (clean, blur/noise, skew/rotation);
- OCR raw output and processing time;
- CER/WER only when a reliable character-level reference transcript is available;
- representative error examples with evidence.

Do not claim SVGs alone cover scanned-PDF or photographed-image routes. Those variants still need to be rendered/created and recorded separately.

## Validation notes

The script checks subtotal + VAT = total and uses stable sample IDs and UUIDs. The v0 generator is intentionally small and uses fictional data. It does not yet generate degraded variants, PDF files, or a separately authored independent mock test set.
