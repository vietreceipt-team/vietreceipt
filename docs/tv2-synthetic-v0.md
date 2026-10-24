# TV2 synthetic data and TV3 handoff (corrected v0.2.0)

Replaces the v0.1 starter implementation from PR #60 without changing historical
data/labels. See docs/data/tv2-status.md for remaining issue #47 acceptance gates.

## Reproduce

Python 3.12. Install requirements-data.txt. Install TV3's documented OCR runtime
separately for image/scan execution. Pass --font to a locally available Unicode
TrueType font (Windows Arial or Linux DejaVu Sans). Record font hash.

```sh
python -m scripts.data.generate_synthetic --out data/synthetic/v0.2.0 --count 30
python -m scripts.data.augment_dataset --root data/synthetic/v0.2.0
python -m scripts.data.validate_ground_truth --root data/synthetic/v0.2.0 --manifest data/synthetic/v0.2.0/rendered_manifest.csv --output results/tv2-local/qa.json
python -m scripts.data.dataset_stats --root data/synthetic/v0.2.0 --manifest data/synthetic/v0.2.0/rendered_manifest.csv --output results/tv2-local/stats.json
python -m scripts.data.reader_smoke --root data/synthetic/v0.2.0 --output results/tv2-local/reader-run --all-routes
python -m scripts.data.package_dataset --root data/synthetic/v0.2.0 --output output/datasets/vietreceipt-tv2-v0.2.0.zip
python -m unittest tests.test_validate_invoice_dataset_v2 tests.test_tv2_data -v
```

Use a new output path for each run; scripts refuse destructive overwrite.
Legacy script entry points forward to the new modules. Dependencies are no
longer described as standard-library-only.

## Contents and semantics

30 base invoices; 6 layout families; 15/5/10 base split. 17 input files per
invoice = text-PDF + 8 conditions x (PNG + image-only PDF), total 510 manifest
rows. Variants are not independent invoices. Each condition has a fixed seed,
parameters, parent, scale and split metadata. Conditions: clean, blur, noise,
rotation, perspective, contrast, scan_like, photo_like.

All 13 canonical headers are emitted. A field intentionally omitted from the
source has UNKNOWN/null, not PRESENT. VAT rate is visible source metadata,
outside the 13-header gold. Rates 0/5/8/10 vary. Every row visibly contains unit.
All text/spec/JSON/CSV bytes are UTF-8 LF; PDF IDs/timestamps are invariant.
Reproduction is byte-stable for identical dependencies and font hash; different
fonts/renderers are a new rendering environment, not expected identical hashes.

## TV3

Use tv3_train.json first. It is directly consumable by
python -m scripts.benchmark_document_reader --manifest ... --output NEW_RUN .
Each variant has a unique id, a path relative to the manifest and full visible
reference transcription. Whitespace-only normalization preserves case/diacritics.
The reader may reorder spatial columns; report reading-order errors separately
from recognition. Preserve failures; do not drop failed samples from denominators.
Run OCR-all/direct-text comparison on the identical eligible PDF set.
Text-PDF extraction is checked against transcript during augmentation.

## TV4 evidence mapping

Source gold intentionally starts with source_block_ids=[]: these are not reader
IDs. TV3 must return actual document-2.0 evidence, then a reviewer supplies a
cell-to-block mapping. scripts.data.link_evidence takes --gold --evidence --review
--output. Review JSON includes approved, reviewed_by, reviewed_at, gold_sha256,
evidence_sha256 and links (cell paths -> actual block IDs). It validates the
linked copy with the existing TV4 validator and preserves source gold.
Never derive gold from KIE predictions or call generated geometry actual OCR.

## Tests and limits

Automated QA checks schema, exactly 13 header keys, source/status consistency,
line/total arithmetic, checksums, duplicate IDs/content, family/parent leakage,
broken files, visible-spec/label/transcript consistency. Regression tests mutate
data to ensure failures are caught. Real text-PDF-to-reader-to-KIE smoke output
is a functional diagnostic, never accuracy evidence. Independent human review
and final independent mocks cannot be replaced by automated tests.
