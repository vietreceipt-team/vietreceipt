# VietReceipt OCR pipeline and evaluation

This module runs a reproducible Vietnamese receipt OCR probe and adapts
engine-specific output to the shared `OCRResult v1.3` contract consumed by KIE,
Backend, and Frontend evidence highlighting. Week 2 adds a callable integration
boundary, immutable evaluation artifacts, semantic invariant checks, and a
field-aware error-analysis harness without changing the frozen shared schema.

## Worker integration entry point

Production orchestration creates one lazy pipeline for each worker process and
injects its bound method into the processing orchestrator:

```python
from ai.ocr import get_worker_ocr_pipeline

ocr_pipeline = get_worker_ocr_pipeline()
orchestrator = ProcessingOrchestrator(
    # Other Backend-owned dependencies omitted.
    ocr_provider=ocr_pipeline.run_ocr,
    ...,
)
```

The process singleton owns one lazily loaded PaddleOCR engine, so Celery task
calls for multiple receipts do not reload model weights. The compatibility
function `ai.ocr.run_ocr` delegates to the same process-long-lived pipeline;
callers may still pass an explicit pipeline for tests or isolated jobs.

`resolved_image` may be a local `Path`, bytes, or an already-decoded PIL image.
The worker/application layer supplies both UUIDs. Benchmark identifiers such as
`R001` are rejected at this runtime boundary. The pipeline performs inference,
adapts the engine response, validates the canonical schema and cross-block
invariants, and only then returns the result.

OCR does not persist database records, update receipt state, retry work, or
resolve object storage. Those responsibilities remain with Backend/worker
orchestration. `ImmutableOCRArtifactStore` exists only for local evaluation and
reproducibility artifacts.

### Reprocess and immutability

A reprocess keeps the same `receipt_id`, receives a new `ocr_run_id`, and
returns a new result. The local artifact store writes to:

```text
<output-root>/<receipt_id>/<ocr_run_id>.json
```

It uses exclusive creation and refuses to overwrite an existing run. Production
persistence must provide the same append-only behavior.

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
document against `schemas/ocr-result.schema.json` before writing it. It also
enforces unique block IDs, contiguous zero-based reading order, unique polygon
points and point order. Missing or malformed polygons fail the run; invalid
artifacts are never returned or saved as canonical.

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

## Field-aware error analysis

Run the Week-2 evaluator with:

```bash
python scripts/evaluate_field_aware.py
```

The input manifest is `data/field_evaluation/manifest.json`; its records link a
KIE/Data-owned annotation record to the exact real OCR result and, when
available, a canonical verified/oracle OCR result. The generated
`results/field_aware_error_report.json` always includes the five canonical
fields, deeper-primary flags for merchant/date/total, sample and quality-stratum
slices, and this taxonomy:

- OCR omission;
- OCR substitution;
- segmentation/grouping;
- reading order;
- geometry/evidence;
- not an OCR error.

The current frozen 40-sample set has first-pass full transcriptions, but no
KIE/Data-owned verified five-field annotation records. The committed report
therefore says `WAITING_FOR_VERIFIED_FIELD_ANNOTATIONS` and reports zero field
cases instead of deriving semantic gold labels from OCR output. Once verified
records are added to the manifest, the same command regenerates the real report.

### Oracle versus real OCR

Each manifest record can provide both `real_ocr_path` and `oracle_ocr_path`.
Both artifacts must validate as canonical OCRResult v1.3 and refer to the same
receipt, but they must be different files with different `ocr_run_id` values.
Oracle availability also requires `oracle_qa_state=VERIFIED` and non-empty
`oracle_provenance`; the evaluator rejects an ordinary canonical OCR JSON being
relabelled as Oracle evidence. This gives KIE a reproducible input pair for
controlled/oracle and real OCR runs. OCR does not invent polygons or set
confidence to `1.0` when verified oracle block evidence is unavailable.

The integration identity contract is final: the worker invokes OCR with a
Backend-generated `ocr_run_id`; OCR consumes that ID and returns the same run
identity.

## Confidence semantics

Block and average confidence are evidence emitted by the OCR engine:

```text
OCR confidence != field confidence != probability that a field is correct
```

OCR confidence must not be used alone to skip human review. Field confidence,
calibration, AUROC/ECE, risk-coverage and review thresholds belong to KIE/Data.

## Annotation QA and experiments

- `pending_review` is never promoted automatically.
- A reviewer and disagreement provenance must be recorded by the annotation
  protocol before an item is described as reviewed.
- Test results and annotations are not edited to improve metrics.
- No preprocessing/model switch was made in Week 2 because verified field-aware
  evidence is not yet available. Future preprocessing changes require a stated
  hypothesis, controlled before/after run, evidence and recorded decision.

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

Week-2 regression tests also cover Backend UUIDs, process-long-lived engine
reuse across multiple worker receipts, reprocess run identity,
immutable artifact writes, semantic contract failures, benchmark-ID isolation,
all six field-error categories, five-field coverage, quality slices,
Oracle/Real availability and reproducibility metadata.
