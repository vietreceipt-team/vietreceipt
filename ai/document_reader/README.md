# VietReceipt TV3 Document Reader V2

Issue [#48](https://github.com/vietreceipt-team/vietreceipt/issues/48).
Images and PDFs become canonical spatial text evidence. No invoice field rules
or dataset-specific IDs occur in the runtime.

## Install and run

Python 3.12, CPU. From repository root:

```sh
python -m pip install -r requirements-document-reader.txt
python -m pip install -r requirements-document-reader-test.txt
python -m unittest tests.test_document_reader tests.test_ocr_contract tests.test_ocr_week2 -v
```

The first image/scan run downloads official Paddle models. Prewarm on the demo
machine while internet is available. `PADDLE_PDX_CACHE_HOME` can point to an
existing local cache. No uploaded document is sent to a cloud inference service.
Direct text-PDF reading does not initialize Paddle.

```python
from uuid import uuid4
from ai.document_reader import DocumentReader

reader = DocumentReader()  # reuse once per worker process
evidence, audit = reader.process_with_metadata(
    "invoice.pdf", content_type="application/pdf",
    receipt_id=uuid4(), ocr_run_id=uuid4(),
)
```

For the TV5 worker from PR #53, install reader requirements in the worker image,
put the repository root and `backend` on `PYTHONPATH`, and set:

```text
V2_DOCUMENT_READER_CALLABLE=ai.document_reader.backend:read_document
```

This optional adapter translates `ReaderError` to TV5's `V2Error`; standalone
callers use `ai.document_reader:read_document`. The signature matches
`configured_reader(data, *, content_type, receipt_id, ocr_run_id)` exactly.
TV4 must consume the document envelope and preserve `source_block_ids`.

## Routing and geometry

- PNG/JPEG: signature validation, EXIF orientation, optional resize/contrast,
  document orientation classifier, Vietnamese PP-OCRv3.
- Text PDF: extract words and glyph geometry directly with PDFium.
- Scan or unusable text layer: render page at 200 DPI RGB, then OCR.
- Mixed document: route each page separately. A large image with a sparse text
  footer is treated as a scan. This is a heuristic, not full intra-page fusion.
- Default limits: 30 MB, 30 pages, 40 million rendered pixels/page and 200,000
  PDF characters/page. Unsupported, corrupt and encrypted inputs fail explicitly.
- IDs unique within run; deterministic row-major ordering; normalized four-point
  polygons TL/TR/BR/BL; every page carries the same receipt/run UUID.
- Orientation uses `PP-LCNet_x1_0_doc_ori`; mapped-back polygons match source.
  `ReaderConfig(orientation="none")` disables it for baseline/ablation. There is
  no silent fallback if the orientation model is unavailable.

PDF geometry is in the cropped, **unrotated** page coordinate system used by the
current TV6 viewer. Image geometry is after EXIF display orientation, before OCR
rotation/resize. See the migration notes for the numeric PDF confidence sentinel.
All engine confidence values are evidence confidence, never field confidence.

## Synthetic demo and visual inspection

```sh
python -m scripts.create_document_fixtures --output results/tv3-fixtures --font /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
python -m scripts.demo_document_reader results/tv3-fixtures/mixed.pdf --output results/demo
```

On Windows use `--font C:/Windows/Fonts/arial.ttf`. Open `results/demo/index.html`:
source pages, clickable evidence polygons and text are displayed locally. This
is a TV3 diagnostic demo, not the product review/verification interface.
The output directory must be new to preserve previous runs.

To inspect a previously saved real prediction without rerunning inference:

```sh
python -m scripts.demo_document_reader results/tv3-fixtures/mixed.pdf --evidence results/run/predictions/mixed-pdf.json --output results/review
```

## Benchmark and ablations

```sh
python -m scripts.benchmark_document_reader --manifest results/tv3-fixtures/manifest.json --output results/baseline --orientation none
python -m scripts.benchmark_document_reader --manifest results/tv3-fixtures/manifest.json --output results/oriented --orientation auto
```

Other independent experiments: `--max-side 1600`, `--contrast 1.2`, `--dpi 150`,
`--force-pdf-ocr`. Compare on the same development manifest; freeze configuration
before any final test. The reader does not split data or alter ground truth.

Manifest fields: dataset/version/split/provenance plus `samples`, each with unique
safe `id`, relative `path`, `condition`, optional transcription `reference`, and
optional `expected_error`. Missing reference yields null metrics, not zero error.
Failures with a reference are scored as empty predictions; failed samples remain
in the report. CER/WER are micro-aggregated after collapsing whitespace only.
Case and Vietnamese diacritics remain significant. There is no field-accuracy
metric or claim of unseen-template generalization in this diagnostic harness.

Artifacts in each new run directory: frozen manifest, configuration/package/model
versions, Git SHA when available, source hashes, UUID-tagged predictions, per-page
audit metadata, metrics by condition and `error_report.csv`. Do not commit private
invoice artifacts. Generated fixtures contain fictional data and an explicit
non-financial-value label.

## Error analysis and limitations

Classify observed errors as omission, substitution, segmentation, reading order,
geometry, PDF extraction or rendering. Inspect overlays alongside transcription
diffs; CER alone cannot diagnose geometry. Report examples affecting amounts and
tax IDs to TV4 without changing the raw OCR text.

The synthetic fixture family shares one template and is **development only**.
It is not TV2's frozen dataset, unseen-layout evaluation or final thesis result.
Automatic orientation is model-based and can fail; perspective correction,
deskew, tiled long-invoice OCR and model fine-tuning remain separate experiments.
Row-major ordering is a baseline and does not reconstruct semantic table rows.
PDFs with garbled but plausible text layers or mixed text/image content on one
page may need `force_pdf_ocr`; no automatic OCR-vs-text semantic comparison occurs.
The module serializes inference/PDFium calls per process; scale via worker
processes and enforce deployment-level timeouts in TV5.

The CI suite uses a clearly labeled fake OCR engine and real PDF extraction and
rendering. Real-model results, if provided, are separate evidence; CI passing
does not demonstrate real OCR quality or the deployed end-to-end workflow.
