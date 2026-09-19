# Evaluation Plan v2

## Evaluation layers

### OCR / text reading
Report OCR/text-reading quality separately from KIE. Use CER/WER where reference transcription exists and record evidence failures that affect downstream extraction.

### Header-field extraction
For every supported canonical field report correct normalized values, misses, wrong values, false values when the source does not contain the field, and unresolved/ambiguous cases. Do not hide weak fields behind one aggregate.

### Line items
Report at least:
- line detection recall (missing/extra rows);
- matched-line cell correctness;
- per-column correctness for description, quantity, unit price and amount.

### Full-invoice completion
Report the number/rate of documents for which all required evaluated fields are correct. Field accuracy does not imply a whole invoice is correct.

### System behavior
Measure:
- upload-to-result processing time;
- failure rate by processing stage;
- export/schema validity;
- robustness slices such as clean, blur/noise, rotated/perspective and scan-like data when those slices exist.

## Dataset reporting
Every result table must name dataset family, exact snapshot/version, split/manifest, sample count, synthetic/public flag, configuration and commit.

CORD/SROIE results are external benchmark results, not evidence of Vietnamese enterprise performance.

## Frozen test rule
Final test manifests are frozen before final tuning. If a test result is inspected and then used to change the algorithm, that test is no longer an untouched final test for the changed version.

## Web demo
The web demo proves functional integration: upload → processing → review → correction → confirmation → export.

Do not claim accountant time savings unless a real manual-vs-tool study is separately designed and executed. A synthetic dry run is not a user study.
