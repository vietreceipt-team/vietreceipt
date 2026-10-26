# TV1 evaluation decisions and owner review record

**Owner:** TV1 / Evaluation Lead\
**Created:** 2026-10-24; refreshed 2026-10-26\
**Status:** TV1 methodology decision *proposal*, submitted for co-sign; **not** G1 pass, dataset QA, result publication or final-test authorization.\
**Related:** [Evaluation matrix](evaluation-matrix.md) · [Research design](research-design.md) · [Pilot protocol](user-study-protocol.md) · [Acceptance tracker](tv1-acceptance-tracker.md) · issues #47, #48, #49, #50, #51, #52 and #59.

## Scope and claim boundary (TV1 decision)

The scored canonical invoice comprises **13 header fields** (invoice template number, symbol, number, date; seller name, tax ID, address; buyer name, tax ID; subtotal, tax amount, total amount, currency) and **five cells per line row** (description, unit, quantity, unit price, amount). Row association is essential: correct values assigned to the wrong item are incorrect. **Tax breakdown groups are excluded from complete-invoice accuracy** until versioned source annotations and evaluation for them exist.

The primary evidence must come from the **original input bytes** through Reader → KIE → immutable, uncorrected machine output, using independently QA'd **Source Gold**. OCR-aligned Gold is for KIE-on-fixed-evidence diagnosis; shared `source_block_ids` do not establish source-level row accuracy. Keep processed/eligible/fully-scoreable denominators separate; keep reviewed human values entirely outside machine accuracy.

## D1 — Values, statuses and metric names (TV1 proposes ADOPT)

- **Exact-value extraction precision/recall/F1** is a *value-aware* metric, not mere field-presence detection. For gold `PRESENT`, a true positive requires predicted `PRESENT` with the correct canonical value. A wrong `PRESENT` value contributes **both FP and FN**. A predicted `PRESENT` against known non-PRESENT gold contributes FP.
- Per field: `TP = correct PRESENT predictions`; `FP = predicted PRESENT on known gold − TP`; `FN = gold PRESENT on known gold − TP`. `P = TP/(TP+FP)`, `R = TP/(TP+FN)`, `F1 = 2TP/(2TP+FP+FN)`. Report TP, FP, FN, coverage and per-field/micro; macro averages only where defined.
- **Presence-only** measures whether a field was marked PRESENT regardless of value; if used, publish it **separately**, never as value accuracy.
- Gold `UNKNOWN` = annotation unavailable: exclude from all corresponding accuracy denominators, show its number and coverage; never count predicted UNKNOWN as correct value. Gold `UNREADABLE` and `AMBIGUOUS` are *known status labels* and may be counted in status+value exactness when predicted state matches; they have no extractable PRESENT value, and their count must be shown separately. `NOT_PRESENT` requires predicted absence, not missing output.
- Keep the repository's existing **known-status exactness** definition as the strict status+value headline *provided every required gold label is adjudicated* (i.e., no UNKNOWN). Do **not** describe a correct UNREADABLE/AMBIGUOUS state as a recovered transcription. Report status mix/coverage alongside strict accuracy so that opaque invoices cannot inflate perceived readable-value extraction.
- Failed eligible inputs remain failures in the processing denominator and fail strict document-level correctness; under labeled PRESENT cells they contribute FNs. Zero denominators are **null**, never automatically 0 or 1.

**TV4 implementation check (26 Oct):** PR #69 is merged in main `07c7cd0`; evaluator 2.2.0 implements UNKNOWN masks, strict denominators and row P/R/F1. Open PR #71 adds auditable field/micro TP/FP/FN, five-state totals and matching boundary tests. The published table/figure titles should say `Exact-value extraction`, not `Presence`. Verify the accepted code/version against these tests; a linked proposal is not merged code or co-sign. No retroactive re-labeling of earlier evaluator versions.

## D2 — Source-region row matching (TV1 proposes DEVELOPMENT CANDIDATE; final freeze BLOCKED)

The implementation candidate merged through PR #69 is `page-bbox-positive-iou-cardinality-1.0`: on the original document coordinate frame, page-aware **positive-area intersection**, maximum-cardinality one-to-one row assignment; **never** predicted/gold values or gold OCR block IDs. Each row's candidate edges are ordered by IoU then prediction-array index before augmenting-path assignment. This local ordering does **not** maximize the total IoU across all maximum-cardinality assignments; prediction-array index is not independently guaranteed to equal source reading order. TV5 PR #70 performs original-file hash/page/coordinate validation upstream.

Freeze the actual assignment objective and ordering, not an assumed global overlap optimum. Development review must include a same-cardinality counterexample with gold bounds `[0,0,1,0.4]`, `[0,0.4,1,0.8]` and predicted bounds `[0,0,1,0.8]`, `[0,0.35,1,0.5]` on page 0. The current traversal has total IoU 0.6; an alternative has 0.722222. Either accept and describe the traversal's limitation after source review, or version a replacement objective. Reordering predictions and changing values must be tested separately; never choose an assignment by whichever gives better cell correctness.

**Do not silently declare this matcher scientifically validated.** The `IoU > 0` candidate can match a barely touching or overly broad box. Before adopting it for scored experiments, TV4 must supply development-only cases and outcomes for: page mismatch, zero-area edge touch, tiny positive overlap, neighboring rows, a merged predicted row overlapping two gold rows, split predictions, multiple optimal assignments, EXIF-rotated image and rotated/cropped PDF frame. Report TP/FP/FN plus sample IDs and coordinates. TV1 and TV2 then either:
1. accept the versioned positive-IoU candidate after reviewing these errors and document its known limitations, **or**
2. register a **new matcher version and threshold chosen solely on development evidence** (including sensitivity comparison) and rerun development tests.

Never tune the threshold after seeing held-out final results. KIE block-ID matching remains a separately named diagnostic.

## D3 — RQ1 speed/correctness claim (TV1 decision: NO non-inferiority claim)

Compare OCR-all and route-aware **on identical born-digital PDF bytes** with identical downstream KIE/configuration. Report paired complete-invoice outcomes and eligible/scoreable n, failures, route/fallback counts, paired median latency and variability, processing environment/commit; cluster any confidence interval by original invoice/template family when data permit.

**No arbitrary accuracy-loss margin or “accuracy preserved” claim.** With no predefined, power-justified non-inferiority margin and independent evidence, describe the observed paired **trade-off**; report intervals and uncertainty. A faster observed median alone is not proof that the method is faster across invoices. RQ1 also reports JPG/PNG and scanned PDF strata separately, not as inappropriate route-aware comparisons.

## D4 — Gold eligibility, leak prevention and final freeze (TV1 decision: ADOPT)

- **Source Gold:** values, statuses, original page/region, file SHA-256, dataset/split/family/parent IDs, annotator and independent QA/adjudication; prepared before seeing model predictions. **OCR Evidence:** frozen Reader output with provenance. **Aligned Gold:** links source labels to a *specific* OCR run/block set and does not rewrite the source labels.
- Declare upload eligibility **before** execution. All eligible original-file failures (timeout, crash, malformed/no output, provenance mismatch) stay in the intended cohort. Excluded unsupported files must be reported separately with predeclared reason; no selective post-hoc removal.
- Field scoring uses known annotation states. Strict complete-header/invoice scoring requires adjudicated known statuses for *every required header and row cell* and complete row inventory. Any required `UNKNOWN` makes the document **unscoreable for strict accuracy**, but it remains in eligible-processing counts. Failed machine runs on otherwise scoreable documents count incorrect. Empty-table ground truth must be explicit. Complete-invoice scope is **13 headers + line items, tax groups excluded**.
- An empty gold array does not attest that the source has no items. Before strict scoring, independently review the complete row inventory and store `confirmed empty` versus `unadjudicated` in the versioned source review/sidecar record, with source hash and reviewer. Annotation-v2 is unchanged; missing evidence must not be encoded by deleting rows. Use the same locked known-label mask for paired methods and show excluded-document coverage by route/family, so a high score on a small scoreable subset is not described as whole-cohort accuracy.
- Augmentations/variants inherit source parent and split. A generator-derived `test` split inspected during development is **not** an untouched final dataset. Final mock must be independently authored and source-verified; freeze source hashes, manifest, annotation, source-region matcher, thresholds, reader/KIE versions, code commits and runtime fingerprint **before** revealing test results.
- One documented primary final run with immutable per-sample machine output and failures. If findings prompt tuning, move subsequent results to exploratory status; a new untouched confirmation set is needed for a fresh final claim.
- CORD/SROIE are external receipt benchmarks; do not equate their results with Vietnamese VAT/company invoices.

## D5 — RQ3 human review (TV1 decision: OPTIONAL, NOT APPROVED)

Follow [pilot protocol](user-study-protocol.md) only with supervisor/institutional approval and applicable consent/privacy safeguards. Use fictional invoices and independent final scoring. If unavailable, write `not conducted`, not a performance conclusion.

## D6 — Same-target normalization and timing (TV1 proposes ADOPT)

E3 compares a frozen minimal parser and proposed normalizer on identical selected candidate strings against the same canonical targets. Literal raw-string equality against canonical gold is a different task; report it only against independent raw-transcription gold. Hold extraction/ranking fixed and publish both gain and harm transitions. Arithmetic warnings are a separate diagnostic with labeled inconsistency cases; count alone establishes no benefit.

For E7, primary task time is an external wall clock with the same handoff-to-output/export endpoints in both conditions. The TV6 `active_review_ms` counter excludes waits and hidden tabs and starts later; it is a secondary effort measure, not a replacement for task time. Define successful edit events, unchanged confirmations and final machine-to-human cell differences separately. Acknowledging a gold-correct UNREADABLE/AMBIGUOUS state is not a failed transcription task; unresolved source labels remain distinct from unresolved participant mistakes.

## Cross-owner review request / sign-off

A GitHub review must state **APPROVE with tested contract version**, identify adopted decisions D1–D6, or enumerate required changes; silence, requested reviewer status, CI green, synthetic demo or software test doubles **do not count** as sign-off. TV1's policy proposal here is not authorization to change other members' algorithms or QA records.

| Role | Must verify | State as of writing |
|---|---|---|
| TV1 | RQs, D1–D6, limits and freeze policy | Draft published for review; no final run authorization |
| TV2 | Source Gold/source regions, labels, split/leakage, independent QA and final mock | PENDING human co-sign |
| TV3 | PDF/OCR route and source coordinate contract, provenance and paired read evidence | PENDING supporting evidence |
| TV4 | Five-state counters, actual row matcher version/edge stress tests, value-blind source metrics | PENDING human co-sign |
| TV5 | Original-file runner, denominator, failure/provenance linkage and fail-closed QA | PENDING human co-sign |
| TV6 | Before/after correction separation and real-provider demo; optional pilot | PENDING for G6/E7 |

**Gate rule:** keep G1 awaiting TV2/TV4/TV5 reviews; G2–G4 awaiting reviewed artifacts and run evidence; G5 CLOSED until G1–G4 pass. Do not close issue #52 or mark the project completed from document creation alone.
