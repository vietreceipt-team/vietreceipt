# Invoice KIE V2 deterministic baseline — TV4 / issue #49

This is implemented extraction code, not an audit or a final evaluation result.
`ai.kie.v2:extract_invoice` accepts canonical evidence and returns the shared
`schemas/invoice-kie-result.v2.schema.json` machine contract. It does not load
PaddleOCR, PDFium, model weights, private datasets or human corrections.

## Run

Use Python 3.12, matching the KIE CI workflow:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-contracts.txt
.venv/bin/python - <<'PY'
import json
from uuid import UUID
from ai.kie.v2 import extract_invoice
with open('examples/invoice-v2-synthetic-evidence.json') as handle:
    evidence = json.load(handle)
result = extract_invoice(evidence, kie_run_id=UUID('00000000-0000-4000-8000-000000000053'))
print(json.dumps(result, ensure_ascii=False, indent=2))
PY
```

The two `examples/invoice-v2-synthetic-*.json` files and all new fixtures are
hand-authored synthetic software tests, **not frozen TV2 gold, real invoices,
an independent test set, or thesis results**. The generated result is checked
against the callable in the shared contract suite.

For TV5 configure `V2_KIE_CALLABLE=ai.kie.v2:extract_invoice`. Its signature is
`extract_invoice(evidence: dict, *, kie_run_id: uuid.UUID) -> dict`.
Malformed evidence raises `ValueError`; an incorrectly typed run argument raises
`TypeError`. The worker's provider boundary handles these failures. There is no
subprocess/stdout parsing requirement and no network activity in extraction.

## Contracts and provider compatibility

Reviewed without merging:

| PR | Inspected head | Interface |
| --- | --- | --- |
| #53 TV5 | `82cd45212d97c3ac03951318687ff7d0481d59b5` | `configured_kie`, `validate_evidence`, `validate_result` |
| #54 TV6 | `f4b31130d9ceb9a2cb1e2b515905c6552c8f3e15` | `evidencePages`, source IDs, polygons, field/review rendering |
| #55 TV3 | `85f509174a6f298f2cd17b529470a4606274040f` | OCRResult 1.3 pages in `document-2.0` |

Issue #49 and integration-contracts take precedence over the incomplete former
V2 schema. The canonical schema now requires `predicted_value`, normalization,
review policy, scoring metadata, root extractor/configuration name+version, and
row review metadata. V2 producer fixtures in dependent PRs must adopt these
required properties when integrating this schema. The current TV5 loader and
validator accept this provider when using the updated shared schema.

Root IDs are copied exactly from evidence (receipt/source OCR run) or the caller
(KIE run); no new receipt identity is inferred. A rerun uses a new caller-owned
KIE run UUID. With the same evidence and UUID, the entire output is deterministic:
no timestamp, duration, random ID, or mutable global configuration is emitted.

The adapter validates the canonical OCR schema, finite numbers, transportable
text, nondegenerate polygons, contiguous reading order per page, exact page/run
identity, contiguous zero-based pages and unique block IDs across the document.
It retains original text/confidence/geometry in frozen internal blocks. The
`pdfium-text` confidence sentinel remains stored as original confidence, while
its internal evidence confidence is `None` (N/A), never a 100% field probability.
It does not rewrite the OCR artifact.

The result validator enforces the schema plus source ID existence/order, exact
raw text reconstructed from source blocks, receipt/run identity, unique line IDs
and row metadata aggregated from cells. JSON Schema cannot enforce cross-record
source membership alone; consumers should call this validator or the TV5 boundary.
PRESENT requires evidence, prediction, non-null normalized value and a rule/version.
Non-PRESENT values and their normalization provenance are null. Human correction,
effective values and verification are not TV4 machine output.

## Architecture and decisions

1. `evidence.py` validates and flattens pages in page/reading order.
2. `extraction.py` identifies table regions, generates label/value candidates and
   identifies seller/buyer roles using preceding section anchors and relative
   horizontal/vertical distance. Tied role anchors produce review uncertainty.
3. `cells.py` ranks candidates deterministically; source order breaks equal-score
   ties. Competing normalized values within 0.1 score produce AMBIGUOUS, preserving
   evidence from the competitors. Equivalent normalized values are not conflicts.
   Currency conflicts always remain unresolved regardless of score differences.
4. `normalization.py` reuses the legacy Candidate/NormalizationResult primitives
   behind canonical V2 names, adding conservative versioned V2 rules.
5. Table rows use page-local vertical overlap (at least 0.35 of the smaller block
   height), relative x alignment to recognized headers, and reading order. Closely
   following description-only text (gap at most 1.8 text heights) joins the previous
   row; all contributing source blocks remain linked and AMBIGUOUS_FORMAT marks
   the possible continuation/partial-item ambiguity. Other incomplete rows remain
   rows, with unknown/unreadable cells and review reasons. No unit column means
   unit NOT_PRESENT; an empty cell in a printed column means UNKNOWN.
6. `consistency.py` compares complete line-amount sums with subtotal, and printed
   subtotal + printed tax with printed total. Absolute tolerance is 1 VND under
   `invoice-consistency-2.0.0`. Checks are PASS/WARNING/SKIPPED; missing operands
   skip checks. Warnings propagate to relevant cells and rows. Values never change.
7. The output is validated before returning it to the worker.

Totals require positive semantic labels; customer-paid/change amounts are not
total candidates simply because they are large. Tax tables and explicit rate rows
support multiple numeric rates (including 0/5/8/10%) and printed KCT/KKKT categories.
Tax group values are not summed to invent an absent header tax amount.

## Normalization and uncertainty

| Rule | Policy / provenance |
| --- | --- |
| Identifiers | Reuse `invoice_id` primitive; NFC, trim/collapse whitespace, retain leading zeros, case and safe separators; legacy rule/version recorded |
| Names/addresses | Reuse merchant name/address primitives behind seller/buyer canonical names; no accent repair, geocoding or abbreviation expansion |
| Date | Reuse calendar validation; ISO or unambiguous numeric day/month; ambiguous `09/10/2026` stays null even with a generic Vietnamese label. Explicit `ngày D tháng M năm YYYY` supplies components. No two-digit-year guessing |
| Money | Reuse total-amount integer parser only with explicit VND evidence; consistent dot/comma/space groups of three. No decimals, mixed separators, negatives or currency conversion |
| Currency | Explicit VND/VNĐ/đ/₫/đồng markers only. Unsupported or competing currencies remain unresolved; amounts cannot be silently labeled VND |
| Tax ID | Remove printed ASCII spaces/dots/hyphens only, requiring 10 or 13 ASCII digits; never repair digits; `tax_id_printed_separators`, `invoice-normalization-2.0.0` |
| Quantity | Non-negative integer or one decimal comma/dot; grouping unsupported; `quantity_decimal_no_grouping`, V2 normalization version |
| Tax rate | Preserve printed percent or supported category; normalize whitespace and decimal comma only; V2 normalization version |

`raw_text` is unmodified source block text joined by newline in page/reading order.
`predicted_value` is the selected candidate before normalization. Every selected
prediction has evidence, including failed normalization. No candidate means UNKNOWN
with NO_CANDIDATE, not a claim that the field is absent. Explicit `không có`,
`không áp dụng`, `N/A`, `none` means NOT_PRESENT. Visible replacement/question-mark
text or a label with no readable value means UNREADABLE. Competing candidates,
uncertain role or unsafe format mean AMBIGUOUS.

Field `confidence` is null. `heuristic_score` is **not a probability**:

```text
0.35 candidate base
+ 0.25 explicit semantic role
+ 0.20 aligned/inline label or table-column support
+ 0.15 successful deterministic normalization
- 0.20 if any actual OCR evidence confidence < 0.5
```

The score is bounded below by zero, rounded to four decimals, versioned as
`invoice-heuristic-2.0.0`; review threshold is 0.8. PDF sentinel confidence contributes
no quality penalty or bonus. Score/threshold are development heuristics, not calibrated
claims. Review policy is `invoice-review-2.0.0`. Every reason is explicit: NO_CANDIDATE,
LOW_CONFIDENCE, MULTIPLE_CANDIDATES, AMBIGUOUS_FORMAT, NORMALIZATION_FAILED,
UNREADABLE_SOURCE, SOURCE_ROLE_UNCLEAR, CONSISTENCY_WARNING, UNSUPPORTED_CURRENCY.

## Evaluation protocol

```bash
.venv/bin/python scripts/evaluate_invoice_kie.py
.venv/bin/python scripts/evaluate_invoice_kie.py --manifest /path/to/authorized/frozen-manifest.json
```

Without eligible data, exit code is **2**, status `WAITING_FOR_VERIFIED_V2_GOLD`,
`evaluated: 0`, and `metrics`, `modes`, `propagation_gap` are null. No metrics file
or fake thesis score is committed. Reports print JSON to stdout. All records are
preflighted before extraction; any missing/unverified/mismatched artifact fails
the entire evaluation closed.

TV2 manifest protocol (illustrative placeholders, not an eligible dataset):

```json
{
  "dataset_family": "TV2-owned-family",
  "dataset_snapshot": "TV2-owned-version",
  "split": "test",
  "synthetic": true,
  "template_regime": "unseen-template",
  "configuration": {"name": "invoice-vnd-baseline", "version": "2.0.0"},
  "frozen": true,
  "frozen_at": "2026-09-29T00:00:00Z",
  "qa_status": "VERIFIED",
  "verified_by": "TV2-verifier",
  "sample_count": 1,
  "records": [{
    "qa_status": "VERIFIED",
    "gold": {"path": "gold/sample.json", "sha256": "TV2-supplied-sha256"},
    "evidence": {"path": "ocr/sample.json", "sha256": "TV3-supplied-sha256"}
  }]
}
```

Gold validates `invoice-annotation.v2.schema.json` plus typed canonical values,
all 13 fields, exact dataset/split identity and source linkage. Each gold row must
have evidence IDs for matching. Records cannot escape the manifest directory.
The evaluator never assigns splits or creates oracle text. Optional
`oracle_evidence` uses the same path/hash object and requires
`oracle_qa_status: VERIFIED`; current paired diagnostics require the same receipt,
block IDs, pages and polygons, with verified text substitutions. Full-document
OCR omissions requiring different geometry need an external matching protocol;
they are not silently treated as paired evidence.

Each of 13 headers reports exact status+normalized-value match, precision/recall/F1,
miss/wrong/false-value/unresolved counts and review rate. A wrong PRESENT value is
both a false positive and false negative. Zero-denominator metrics are null.
Rows are matched one-to-one by maximum cardinality of shared annotated source IDs,
with overlap/source order tie-breaking, independent of the predicted cell values.
The report includes:

- line detection recall = matched / gold rows;
- extra-row rate = unmatched predicted / predicted rows;
- matched-row cell correctness and correctness for each of five columns;
- complete-line accuracy = fully correct matched rows / all gold rows;
- complete-table, complete-header and complete-invoice accuracy.

Real/oracle metrics are separate; a per-field oracle-minus-real gap is emitted only
for a fully paired sample set. Error taxonomy counts include candidate, role,
normalization, row/cell alignment, ambiguity and consistency symptoms. These are
automatic diagnostic categories, not verified causal annotations. OCR_PROPAGATION
counts header errors corrected by verified oracle text only. Dataset snapshot,
split, synthetic flag, template regime, manifest hash, configuration, evaluator/
extractor versions, git commit, dirty flag and implementation content hash are
recorded. Reports from synthetic data are labeled `synthetic_diagnostic` regardless
of scores; none substitute for an end-to-end thesis benchmark.

## Migration and limitations

| Action | Decision |
| --- | --- |
| KEEP | V1 callable, schema, producers, unit/evaluation/artifact tests; reusable normalization primitives |
| CHANGE | Complete the one canonical V2 schema, shared validators/examples/CI; new V2 names and full provenance |
| REMOVE | No V1 files removed. Five-field assumptions removed from the new V2 path, not expanded into V1 |
| ADD | Evidence adapter, 13 headers, tax groups, grouped rows, review/scoring policy, arithmetic warnings, fail-closed V2 evaluator |

Baseline limits: recognized Vietnamese/English labels, one logical value per OCR
block/table cell, page-local tables with repeated headers on continuation pages,
and simple aligned columns. Merged multi-column OCR blocks, complex spanning cells,
unlabeled company names, arbitrary header-free tables and ambiguous description
continuations need further extraction work. Close description-only partial items
can be grouped as continuation text with a review warning; evidence is preserved, but row-count accuracy
must be measured on authorized gold. No claims of template generalization are made.
VND context must be explicit; missing currency intentionally leaves money unresolved.

Completed: deterministic code, shared contract, synthetic tests and provider-seam
verification. External acceptance still requires TV2 frozen verified V2 gold and
untouched template-disjoint manifests, plus a running TV3/TV5/TV6 integration for
image/PDF → worker → review → export with actual providers. No real OCR E2E,
deployment, user study or final-test result is implied by these unit fixtures.
