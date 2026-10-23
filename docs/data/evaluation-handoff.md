# Evaluation handoff

## OCR / TV3

Use the generated tv3_train.json with the existing reader benchmark. References
contain the complete visible text, not only extracted fields. Train/dev runs
may compare OCR-all and direct PDF extraction on identical sample IDs. Report
CER/WER, processing failures, reading order and latency per source/condition.
An expected failure must remain visible; do not remove failed samples.

## KIE / TV4

Do not feed unlinked source gold into the strict KIE evaluator. TV3 returns actual
evidence; a human reviews source-cell-to-block links, then link_evidence produces
a validated copy. The existing scripts/evaluate_invoice_kie.py accepts verified
frozen manifests; do not label a development set frozen just to bypass its gate.

The existing evaluator computes per-header metrics, matched-row cell metrics,
row detection, complete header/table/invoice and error taxonomy. Its frozen
manifest contract uses dataset_family, dataset_snapshot, split, synthetic,
template_regime, frozen, frozen_at, qa_status, verified_by, configuration,
sample_count, records. Each record carries qa_status=VERIFIED and gold/evidence
artifact objects with path and sha256 (see ai/kie/v2/evaluation.py::load_artifact).
Dataset inventory freeze is separate from this evidence-linked manifest.

Public imports export a supported_fields mask. Unsupported UNKNOWN fields are
not failures. The strict 13-field evaluator currently has no public eligibility
mask, so partial CORD/SROIE/Vietnamese row labels must not be scored through it
as full canonical invoices. Use scripts.data.evaluate_partial_public for reviewed
development evidence/predictions, or native-task metrics. The additive masked
runner does not change TV4's strict full-invoice evaluator.

```sh
python -m scripts.data.evaluate_partial_public --manifest reviewed_public_development.json --output public_report.json
```

Its manifest has purpose=development, dataset_family, dataset_snapshot, split,
template_regime and records. Each record has qa_status=VERIFIED, reviewed_by,
supported_fields and gold/evidence/prediction artifacts (path + sha256). Header
mask names are canonical keys; row-mask names are line_items.description,
line_items.quantity, etc. Present cells require reviewed actual source_block_ids;
the linker supports public gold without inferring a currency. Only supported
PRESENT cells are scored. Row detection uses one-to-one evidence overlap; cell
accuracy is conditional on matched rows. Full canonical invoice accuracy stays
null for partial datasets. Unreviewed/incomplete inputs produce WAITING.
Preserve native labels and have TV4 review the protocol before formal use.

## Tables

Run a separate verified manifest for every dataset/version and each desired
quality/source/template slice. Preserve its JSON report. Export a comparison
table without averaging unrelated datasets:

```sh
python -m scripts.data.evaluation_tables --reports RESULTS_A.json RESULTS_B.json --output results/tv2-local/tables-v1
```

Incomplete reports remain WAITING; no invented accuracy is written. Preserve
commit, manifest/report hashes, configuration, date, sample count, failure count
and exact sample membership. Use the identical set for ablation comparisons.
The current exporter preserves available provenance but is not an end-to-end
batch evaluator; TV5 owns original-file pipeline failure accounting.
