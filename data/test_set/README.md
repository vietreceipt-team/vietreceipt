# Frozen Week-1 OCR probe manifest

This directory describes a fixed 40-sample selection from the RIVF 2021
MC-OCR Vietnamese receipt dataset. The manifest and SHA-256 values are kept for
auditability; the receipt images are intentionally not distributed by this
repository.

## Composition

- `standard_mixed_layout`: 20
- `challenge_low_contrast`: 5
- `challenge_low_sharpness_or_distance`: 5
- `challenge_lighting_or_perspective`: 5
- `challenge_long_receipt`: 5

The metric-based strata are sampling aids, not audited semantic labels. Manual
merchant and quality labels remain blank until reviewed.

## Source, snapshot, and license

- Source dataset: **RIVF 2021 Mobile-Captured Image Document Recognition for
  Vietnamese Receipts (MC-OCR)**, maintained by VNDAG/VietNLP.
- Source snapshot used by the original local probe: directory label `data0.7`;
  exact download date and upstream archive checksum were not recorded, so this
  legacy provenance gap is stated rather than guessed.
- Sample identity: `source_file`, dimensions, and per-image SHA-256 are recorded
  in `test_manifest.csv`; `SHA256SUMS.txt` verifies an authorized local copy.
- Official dataset page:
  <https://www.rivf2021-mc-ocr.vietnlp.com/dataset>
- Official competition agreement:
  <https://competitions.codalab.org/competitions/27798>

The official terms allow registered research use and explicitly prohibit
distribution, copying, hosting, transfer, or disclosure of the supplied data to
third parties. A third-party Kaggle mirror reports an unknown license and is not
used as redistribution authority. Therefore:

- `data/candidates/`, `data/test_set/images/`, and derived contact sheets are
  excluded from Git tracking;
- Git LFS is **not** used, because LFS would still redistribute the restricted
  files;
- each developer must obtain access through the official agreement and keep
  images in authorized private/local storage;
- no replacement image may reuse an existing `test_id` or checksum.

## Authorized local reconstruction

1. Register for MC-OCR access and accept the official dataset agreement.
2. Place the authorized `data0.7` snapshot at `data/raw/data0.7/`.
3. Run `python scripts/lock_test_set.py --reconstruct-existing` to copy the
   exact files named by the committed manifest into the ignored
   `data/test_set/images/` directory and verify every SHA-256 value.
4. Verify all local images against `SHA256SUMS.txt` before running the baseline.

Do not commit the reconstructed images. If the frozen set must change, create a
new versioned manifest and document the reason, source snapshot, and hashes.

## Ground truth and evaluation scope

Only seven samples currently have non-empty first-pass transcriptions. The
evaluation is therefore a **preliminary Week-1 probe on 7/40 samples**, not a
performance estimate for the full frozen set. Annotation and QA policy lives in
`../ground_truth/README.md`; coverage, missing IDs, normalization, sampling
rationale, and macro-average metric semantics are emitted by
`scripts/evaluate.py` into `results/evaluation_report.csv`.
