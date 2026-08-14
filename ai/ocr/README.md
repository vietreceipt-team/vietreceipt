# VietReceipt OCR Week-1 baseline

This module runs a reproducible Vietnamese receipt OCR probe and adapts
engine-specific output to the shared `OCRResult v1.3` contract consumed by KIE,
Backend, and Frontend evidence highlighting.

## Pinned environment and model configuration

| Component | Pinned value |
| --- | --- |
| Python | CPython 3.12.13 (`.python-version`) |
| PaddlePaddle CPU package | `paddlepaddle==3.0.0` |
| PaddleOCR Python package | `paddleocr==3.0.3` |
| PaddleX pipeline package | `paddlex==3.0.3` |
| OCR model family | `PP-OCRv3` |
| Language configuration | `vi` |
| Document orientation classifier | disabled |
| Document unwarping | disabled |
| Text-line orientation | enabled |
| MKL-DNN | disabled for a portable CPU probe |

The PaddleOCR package version and the PP-OCR model family are different
concepts. `engine.version` in canonical output is the Python package version
(`3.0.3`); the model and language configuration are experiment provenance.
PaddleOCR 3.0.3 does not offer a `vi` model under PP-OCRv4, so this probe pins
the officially supported `PP-OCRv3` + `vi` combination rather than mislabeling
the model as v4.

## Setup

Create a fresh environment with Python 3.12.13:

```bash
python -m venv .venv
```

Activate it, then install exact direct dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

PaddleOCR downloads the selected official PP-OCRv3 models on first use. Receipt
images are not in Git because the MC-OCR agreement prohibits redistribution;
follow `data/test_set/README.md` to reconstruct an authorized local test set.

## Run baseline

Standalone benchmark mode keeps `R001`, etc. only as `test_id` metadata. It
creates canonical UUIDs separately and records the mapping outside OCRResult:

```bash
python scripts/run_baseline.py
```

Run one authorized sample:

```bash
python scripts/run_baseline.py --image data/test_set/images/R001.jpg
```

Integration mode uses UUIDs supplied by Backend:

```bash
python scripts/run_baseline.py \
  --image /private/path/receipt.jpg \
  --receipt-id 31915ef1-6fb4-4e7d-b6f5-53be51c50e3d \
  --ocr-run-id b3ac8bb4-6383-4b97-9911-5a6900054608
```

The adapter applies EXIF orientation before inference, emits clockwise polygon
points ordered top-left, top-right, bottom-right, bottom-left, and validates each
document against `schemas/ocr-result.schema.json` before writing it. Missing or
malformed polygons fail the run; invalid artifacts are never saved as canonical.

## Evaluate the provisional full probe

```bash
python scripts/evaluate.py --require-complete
```

The report records expected/evaluated counts, evaluated and missing sample IDs,
invalid OCR artifacts, sampling rationale, whitespace normalization, annotation
QA scope, and macro-average CER/WER. All 40 frozen samples currently have a
non-empty first-pass transcription and a canonical OCR output, so complete
coverage is expected.

Independent annotation QA is still pending for all 40 samples. The current
metrics are therefore a **provisional 40/40 first-pass baseline**, not final
reviewed benchmark results.

## Contract and module impact

Canonical output is `OCRResult v1.3`:

- UUID `receipt_id` and `ocr_run_id`;
- package name/version under `engine`;
- oriented image dimensions;
- non-empty blocks with normalized four-point polygons, confidence, opaque
  string IDs, and unique zero-based reading order;
- average confidence and duration.

This output directly affects KIE source evidence, Backend run persistence, and
Frontend polygon highlighting. Any shape or semantic change must be coordinated
through the shared schema rather than introduced in the PaddleOCR adapter alone.

## Verification evidence

`results/reproducibility_log.txt` records the exact verification commands and
results for the 40 committed artifacts. The regression suite validates every
artifact against `OCRResult v1.3`, checks mapping UUIDs, unique block IDs,
sequential reading order, and normalized four-point polygons.
