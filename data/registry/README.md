# Public dataset selection and audit (23 October 2026)

Recommended working sources, now recorded in datasets.yaml:

| Family | Publisher/organizer | Use | Local audit |
| --- | --- | --- | --- |
| Vietnamese Bill Extraction | [minhduc168/dataset-origin-vlm-extract-bill](https://huggingface.co/datasets/minhduc168/dataset-origin-vlm-extract-bill) | Vietnamese service rows; MIT declared on card | 10 native train samples imported and mapped |
| CORD | [naver-clova-ix/cord-v2](https://huggingface.co/datasets/naver-clova-ix/cord-v2), [maintainers](https://github.com/clovaai/cord) | Indonesian receipt line items, external benchmark; CC-BY-4.0 | 10 native train samples audited; 7 mapped, 3 rejected |
| SROIE | [ICDAR 2019 organizers](https://rrc.cvc.uab.es/?ch=13) | Native OCR/KIE receipt benchmark | Official access terms/archive still pending |

These are a working proposal for the lead; no source was posted to GitHub or
announced as the team's approved choice. Imported counts are small train subsets,
not full dataset coverage. The original Vietnamese publisher dataset was located
after initially finding its converted instruction variant. The native source
contains image, source_image and master_data. Empty native cells remain UNKNOWN.
Dot/comma thousands formats both occur; mapping version explicitly normalizes
grouped integer VND money and rejects mixed malformed grouping. Sparse item labels
are not full-page OCR transcription, and service receipts are not VAT invoices.

## Pinned snapshots actually downloaded

- Vietnamese: d24586e71318dec13c69f5f35f3d8bc04c5e561c
- CORD: 7f0115a4b758a71d6473b8d085751692da2fef98

Committed snapshot audit JSONs preserve shard, card and export hashes. Original
images/native labels remain under ignored data/raw and data/processed.
CORD's public subset has official 800/100/100 split, not the full collection.
Only the first train shard was downloaded and its first ten samples selected for
this audit. No public test data was used for tuning. Original sample IDs and
native labels are retained. menu.unitprice is unit price; menu.price is row total.
Numeric quantity may have the native x suffix. CORD's rejected rows contain
40,000., Rp0.000 or @20.000; these need semantic review, not silent label changes.
Nested submenus/discount structures remain native and need additional mapping.

The SROIE official site could not be accessed in this session. Exact authorized
archive, terms, hashes and counts must be recorded from the official download;
differing mirror counts are not used to invent a snapshot. The local importer
supports task-3 company/address/total. Date normalization needs a reviewed format.
Keep task-1/2 boxes and transcription for native OCR evaluation.

## Reproduce downloads and mapping

Install requirements-data-public.txt, then use a new directory:

```sh
python -m scripts.data.download_public_subset --family vietnamese_bill --revision d24586e71318dec13c69f5f35f3d8bc04c5e561c --out data/raw/vi-audit --limit 10
python -m scripts.data.download_public_subset --family cord --revision 7f0115a4b758a71d6473b8d085751692da2fef98 --out data/raw/cord-audit --limit 10
```

The default budget is 600 MB per downloaded shard, not per selected sample.
Selection is deterministic from one pinned native train shard; no data are
redistributed by Git. An existing output directory is refused.

The importer accepts UTF-8 JSONL with id, official split, image_path (relative
to --source-root), annotation (native master_data / CORD ground_truth / SROIE
task-3 JSON). Native download/export is automatic for the two HF sources above;
SROIE must be supplied from the authorized archive.

```sh
python -m scripts.data.prepare_vietnamese_bill --input data/raw/vi-audit/export.jsonl --source-root data/raw/vi-audit --out data/processed/vi-v1 --snapshot d24586e71318dec13c69f5f35f3d8bc04c5e561c --source https://huggingface.co/datasets/minhduc168/dataset-origin-vlm-extract-bill --license-note "MIT declared by publisher; preserve attribution and native labels"
```

Equivalent prepare_cord / prepare_sroie entry points exist. Output: source image,
native annotation, partial canonical source gold, manifest, hashes, supported-field
mask and rejection report. Always inspect rejected counts and exit status.
A partial public annotation is not verified full canonical gold. Use native-task
or explicitly masked metrics, not the strict full-invoice evaluator. Do not infer
tax IDs, currency or missing values from country or another document.
