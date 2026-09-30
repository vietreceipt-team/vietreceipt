# TV3 Document Reader V2 — development benchmark

Run date: 24/09/2026 (Asia/Saigon)

Commit: `8caf8d5ea7bb325bfc5c8d5edaf87bbd923535b8`

Dataset: `tv3-synthetic-diagnostics` v1.0, development split

## Scope and interpretation

This report verifies that the real local reader routes image, text-PDF, scan-PDF
and mixed multi-page inputs and records reproducible outputs. It is an engineering
diagnostic using one fictional invoice template. It is not TV2's frozen final set,
not an unseen-layout evaluation and not evidence of generalization.

The transcription comparison collapses whitespace only. Case and Vietnamese
diacritics remain significant. CER/WER are micro-aggregated for referenced
samples. The deliberately corrupt PDF is an expected typed failure and has no
reference transcription. OCRResult confidence is not invoice-field confidence.

## Configuration

- Python 3.12.14 on Windows CPU.
- PaddleOCR/PaddleX 3.0.3, PaddlePaddle 3.0.0, Vietnamese PP-OCRv3.
- PDFium 5.12.1; scanned PDF rendered RGB at 200 DPI.
- Oriented configuration: `PP-LCNet_x1_0_doc_ori`, OCR text-line orientation off.
- No resize, contrast enhancement, perspective correction or fine-tuning.
- Input variants: clean PNG, compressed JPEG, Gaussian blur, deterministic noise,
  perspective warp, text PDF, scan PDF, mixed PDF, 90/180/270-degree rotations,
  and a corrupt PDF.

## Results

| Slice | Samples | Baseline CER | Oriented CER | Oriented WER |
|---|---:|---:|---:|---:|
| Text PDF | 1 | 0.00% | 0.00% | 0.00% |
| Clean image | 1 | 15.95% | 15.95% | 64.06% |
| JPEG/photo-like | 1 | 19.63% | 19.63% | 71.88% |
| Blur | 1 | 16.87% | 16.87% | 68.75% |
| Noise | 1 | 15.95% | 15.95% | 64.06% |
| Perspective | 1 | 15.34% | 15.34% | 62.50% |
| Scanned PDF | 1 | 16.26% | 16.26% | 64.06% |
| Mixed PDF | 1 | 8.12% | 8.12% | 32.03% |
| Rotations 90/180/270 | 3 | 81.70% | 15.95% | 64.06% |
| All referenced samples | 11 | 30.10% | 13.67% | 54.30% |

All 11 readable variants returned schema-valid evidence. The corrupt PDF returned
the expected `PDF_READ_FAILED`. The exact evidence validator from TV5 PR #53
accepted nine earlier real outputs from the same reader contract, including image,
text-PDF, scan-PDF, mixed-PDF and rotation cases.

The orientation ablation is the one clear component contribution in this small
diagnostic: rotation-slice CER falls by 65.75 percentage points. Other slices are
unchanged because their predicted orientation is zero. Text-PDF direct extraction
is both faster in this run (68 ms) and exact for this generated PDF; OCR paths take
roughly 8.6–13.3 seconds after model warm-up on this machine.

## Error analysis

The OCR engine preserves amounts such as `50.000`, `100.000` and `143.000`, but
frequently substitutes Vietnamese diacritics in the synthetic rasterized font.
This explains why character error is materially lower than word error. Direct PDF
text avoids those substitutions. Geometry overlays were inspected for both pages
of the mixed PDF and align with the source at PDF rotation 0.

No conclusion about real invoice quality should be drawn from the perspective/noise
numbers: each slice contains the same single template, and the chosen synthetic
degradation may be too mild. Next evaluation must use TV2's licensed public or
synthetic multi-template development split, followed by a frozen test run after
configuration is fixed. Error reporting should retain omission, substitution,
segmentation, reading-order, geometry, PDF-extraction and rendering categories.

## Reproduce

See `ai/document_reader/README.md`. The benchmark command writes the frozen
manifest, Git/source hashes, package/model configuration, per-document predictions,
page metadata, `metrics.json` and `error_report.csv` to a new ignored run directory.
