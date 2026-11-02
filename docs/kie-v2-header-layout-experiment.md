# Header/Metadata layout experiment — 02/11/2026

## Scope and baseline lock

This branch starts from `42356ad82d6688b1956d8207405f4b6a6613be4f`.
The unchanged worker provider is `ai.kie.v2:extract_invoice`, configuration
`invoice-baseline/2.1.0`, extractor `deterministic-invoice-kie/2.0.4`.
Its output remains byte equivalent on the 12 pre-change fingerprint fixtures in
`tests/fixtures/kie49/baseline-sha256.json`. `header_candidates()` moved from
`extraction.py` into `header.py` without baseline logic changes; the old import
remains available to internal callers.

The input is canonical OCRResult 1.3 or `document-2.0` evidence, including text,
polygons, page and reading order from OCR or direct PDF text. Output is the
unchanged Invoice KIE V2 machine schema, with exactly these 13 non-line-item
fields: `invoice_template_number`, `invoice_symbol`, `invoice_number`,
`invoice_date`, `seller_name`, `seller_tax_id`, `seller_address`, `buyer_name`,
`buyer_tax_id`, `subtotal`, `tax_amount`, `total_amount`, `currency`. Totals and
currency may come from the footer. This is distinct from the superseded V1
five-field receipt contract.

Baseline candidate behavior characterized by tests:

- label/value in one block and in separate same-row blocks;
- seller/buyer anchors, generic MST/address and an unassigned MST flagged for review;
- multiline name/address and unique company letterhead above an invoice title;
- currency markers and conservative VND inference; explicit totals below a table;
- duplicate candidates retained and surfaced as ambiguity;
- table blocks excluded from header candidate extraction, while footer blocks remain.

`select()` preserves the existing status policy: `UNKNOWN` when no candidate,
`NOT_PRESENT` for explicit absence, `UNREADABLE` for unreadable text, `AMBIGUOUS`
for failed normalization or unresolved competing values, and `PRESENT` for a
supported value. No OCR character repair, arithmetic fill or human correction
is introduced. Source text, geometry and IDs remain immutable; emitted
`raw_text` is exactly the ordered text of emitted source IDs. Confidence stays
null; heuristic score is versioned and is not a calibrated probability.

## Variant

`ai.kie.v2:extract_with_layout` is an opt-in internal entry point with the same
evidence/run arguments. Configuration `invoice-layout-header/0.1.0` and
extractor `deterministic-invoice-kie/2.3.0` identify its output. It uses the
same candidate generation, normalization, table grouping and consistency code
as baseline. It reuses the existing `Tên hàng / dịch vụ` table-label alias
from the grouping experiment **only to locate the table boundary**; line rows,
exclusion IDs and tax groups still come from baseline grouping. Its only new
ranking signal is a 0.12 candidate score penalty when a
duplicate candidate for an identity field lies after the detected table start,
or a duplicate subtotal/tax/total candidate lies before it. With no table,
the page midpoint is a fallback boundary. Currency has no region preference.
The penalty applies only when at least one candidate is in the preferred region.
Every candidate remains eligible; a sole candidate is never suppressed due to
region. A resolved conflict retains source IDs for both alternatives and the
existing `MULTIPLE_CANDIDATES` review reason, with `PRESENT` machine value.
`score_version=invoice-layout-heuristic-0.1.0` distinguishes these header scores.

The repo already has `source_row_regions` for **line-row evaluation**. This
variant does not introduce a second public region contract or consume gold
regions at inference. Internal table headers supply the region hint.

## Evaluation protocol and current result

The paired evaluator uses the same evidence, gold, KIE run identity,
normalization and metric implementation for both variants. The manifest must
contain frozen, verified aligned gold and this exact declaration:

```json
{
  "protocol": "header-layout-ab-0.1",
  "evaluator_version": "invoice-evaluation-2.2.0",
  "configurations": {
    "geometry_grouping_v2": {"name": "invoice-baseline", "version": "2.1.0"},
    "layout_header_v0_1": {"name": "invoice-layout-header", "version": "0.1.0"}
  }
}
```

The evaluator refuses A/B on the final `test` split and withholds **all**
scores on any failed or ineligible record. For each field, exact match is
correct status **and** normalized value divided by gold cells whose annotation
status is not `UNKNOWN`. `header_micro_accuracy` sums those correct/scored
counts across 13 fields. `complete_header_accuracy` uses documents with all
13 fields scorable. `complete_invoice_accuracy` includes the 13 fields and
line items; tax-breakdown groups are not scored by it. The source-level failed
input denominator remains the evaluator's documented protocol. Keep seen and
unseen templates and input routes as separate slices; do not tune on final.

Commands:

```bash
python3.12 scripts/evaluate_invoice_kie.py --print-header-experiment
python3.12 scripts/evaluate_invoice_kie.py --compare-header \
  --manifest data/invoice_v2/manifest.json --output NEW_RUN_DIRECTORY
```

On 02/11/2026, the default manifest was absent. The actual run exited 2,
reported `WAITING_FOR_VERIFIED_V2_GOLD`, evaluated 0 and returned null metrics;
see [availability report](experiments/kie-header-layout/availability/report.json).
The TV2 handoff described in `docs/kie49-tv2-intake.md` remains
`PENDING_REVIEW`; its source/row-region and gold–evidence alignments are not
independently signed off. Neither a frozen flag nor output counts are gold QA.

Synthetic diagnostics prove mechanism only: a hand-authored case with two
scored fields (`invoice_number`, `total_amount`) changes header micro accuracy
from 0/2 to 2/2 while retaining competing evidence and review flags. A second
synthetic evaluator test reports delta 0 on one ordinary fixture. Saved PDFium
text and OCR fixture tests verify unchanged source and line/tax output. These
are software regressions, **not** representative accuracy or a promotion case.
An unscored, hash-checked replay of the pending TV2 handoff processed all 60
train and 20 validation evidence files with zero extraction/contract failures.
It changed `invoice_number` from `AMBIGUOUS` to `PRESENT` on 24 train and 4
validation inputs; no other field changed. See the [train replay](experiments/kie-header-layout/train-replay.json)
and [validation replay](experiments/kie-header-layout/validation-replay.json).
These are output transitions, **not correctness gains**: the aligned gold still
needs independent QA. Reproduce with:

```bash
python3.12 scripts/inspect_header_layout.py \
  --root results/kie49/received/tv4-dev-v1 --split train
python3.12 scripts/inspect_header_layout.py \
  --root results/kie49/received/tv4-dev-v1 --split validation
```

The baseline remains the production provider until a reviewed paired
train/validation comparison supports a decision.

Verification on Python 3.12.15 with `requirements-contracts.txt` plus
`reportlab`/`pypdfium2`: 98 targeted tests passed (including the real PDFium
Reader test), contract suite passed, and
the unavailable-manifest evaluator failed closed as described above. GitHub
issues #47, #49 and #59 were read on 02/11/2026; all remain open and require
verified data and independent evaluation for final acceptance.
