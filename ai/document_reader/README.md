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

For the integrated TV5 worker, install `backend/requirements-ai.txt` (combines
backend and OCR dependencies without conflicting validator pins), put the repository
root on `PYTHONPATH`, and set:

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
- Text PDF: extract glyph/word geometry directly with PDFium, then join adjacent
  words on overlapping baselines into spans using font-relative gaps. Column
  gutters remain separate; KIE can match multiword labels without a demo adapter.
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

## Paired route experiment — issue #48 (23/10/2026)

```sh
python -m scripts.compare_pdf_routes --manifest results/tv3-fixtures/manifest.json --output results/dev/document-reader-v2/local-paired-run --orientation auto
python -m scripts.verify_reader_handoff --run-dir results/dev/document-reader-v2/local-paired-run --output results/dev/document-reader-v2/local-handoff-check
python -m unittest tests.test_compare_pdf_routes tests.test_document_reader tests.test_ocr_contract tests.test_ocr_week2 -v
```

Both modes read identical bytes, with matching input SHA-256 and stable receipt
identity but separate run UUIDs. `ocr_all` bypasses the PDF text layer completely;
`route_aware` uses the existing per-page router. All images stay on the OCR path.
The script accepts development/dev/validation only, never a final test manifest.
Manifest sample paths must stay inside the manifest directory. Supply an optional
`receipt_id` per sample to retain TV2's existing canonical UUID.

Each mode keeps the complete predictions, page audit, frozen manifest, input
hashes, package/configuration information and metrics. Top-level outputs:

- `comparison.json/csv`: paired CER/WER, failure status, character deletions,
  substitutions and insertions, timings and cold-start markers.
- `pages.csv`: actual route, fallback, reason, PDF extraction/render/OCR/orientation
  latency; PDF text confidence is empty (`N/A`), while its wire sentinel remains 1.
- `handoff.json`: exact receipt/run IDs, source/evidence hashes and prediction
  locations for TV2/TV4. Ground-truth alignment remains pending TV2 QA.
- `error_examples.json`: text differences with contexts and actual page/block IDs,
  polygons and reading order. These are review candidates; geometry and order
  cannot be diagnosed from CER alone. Never treat an absent block as ground-truth
  `NOT_PRESENT`.
- `runtime.json`: native results pointer and explicit Docker smoke status.

Each mode runs serially in a fresh reader; the first OCR request includes lazy
model startup and is marked `cold_start_candidate`. Do not mix that request with
warm inference for a speedup claim. One pass is a diagnostic, not a latency
distribution. The command exits nonzero on any unexpected read failure while
preserving that sample in denominators (empty prediction when referenced).

The generator v1.1 adds tilted image, two-page text PDF and two-page scan PDF to
the existing single-template diagnostics. It does not replace TV2's independent
development set. See [handoff and runtime notes](../../docs/tv3-issue48-handoff.md).
