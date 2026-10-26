# VietReceipt evaluation matrix

**Protocol status:** refreshed 26 Oct 2026 against main `07c7cd0` and current PRs; not yet co-signed by TV2, TV4 and TV5. This file defines what must be agreed before a final run; it is not a result report. No independently reviewed end-to-end accuracy values are available from this protocol.

## 1. Research questions and claim boundaries

| ID | Research question | Experiment | Primary outcome | Planned report artifact | Result/status |
|---|---|---|---|---|---|
| RQ1 | On the same born-digital PDFs, what are the paired correctness, latency and failure trade-offs of route-aware reading versus rasterize-and-OCR-all? | E1 paired OCR-all vs direct-PDF-text routing | Paired complete-invoice correctness difference; terminal latency difference; failure difference | Table 1: paired method outcomes and route/fallback counts | Source-gold accuracy not scored; Reader-only development captures exist |
| RQ2 | How does the integrated pipeline perform on structured rows across seen, unseen and independently authored layouts and image-quality slices, and which errors account for failures? | E2 grouping ablation; E3 normalization; E4 layout shift; E5 degradation; E6 independent mock | Row precision/recall/F1; complete-line/table/invoice; field metrics; failures by slice | Table 2: outcome matrix; Figure 1: per-template results; Figure 2: error counts | Not run; source gold and reviewed final split are missing |
| RQ3 (optional) | In a small controlled pilot, how does assisted review compare with manual processing in task time, final correctness and corrections? | E7 counterbalanced within-participant pilot on matched fictional invoices | Paired task time, final correctness and correction count | Table 3: descriptive participant/task results | Not run; requires supervisor approval and participants |

RQ1 tests a method contrast only on eligible born-digital PDFs. JPG/PNG and scanned PDFs are still reported as separate end-to-end route strata, but they do not become an OCR-all-vs-route-aware comparison unless the same original documents support both modes and only the declared reader mode differs.

For RQ2, the current geometry grouping is the control for any proposed grouping change. A flat value list may be shown as a qualitative baseline, but it has no row or complete-line score; do not invent row matches for it. E2 must compare two row-producing versions on identical OCR evidence and then confirm the result end to end.

## 2. Evaluation scope and gold contracts

### Canonical scope

The current KIE contract has 13 header fields: invoice template number, invoice symbol, invoice number, invoice date, seller name, seller tax ID, seller address, buyer name, buyer tax ID, subtotal, tax amount, total amount and currency. It has five line-item cells: description, unit, quantity, unit price and amount.

Tax breakdown groups are not present in the current annotation-v2 schema. Until a versioned tax-gold contract exists and is independently checked, every complete-invoice result must be labeled **13 headers + line items; tax groups excluded**. Do not call this tax-complete invoice accuracy. Record tax results as not scored, not as zero or success.

### Two different annotation layers

| Layer | Annotated from | Purpose | Required information |
|---|---|---|---|
| Source gold | Original uploaded bytes, before viewing model output | End-to-end reader + KIE evaluation | File hash; sample/dataset/split/template/parent IDs; field and row canonical values/statuses; original page and normalized source regions; annotation version; reviewer/adjudication provenance |
| OCR-aligned gold | A frozen, identified reader output, after source gold is locked | KIE-only diagnostic on fixed OCR evidence | Source-gold cell identity/value retained; reader run and version; matched OCR block IDs; alignment status and reason for unmatched or ambiguous alignment |

Source gold must not depend on OCR block IDs. Aligned gold may link to them, but missing OCR text or geometry is an alignment/OCR miss; it is never silently relabeled NOT_PRESENT or removed from the end-to-end denominator. Annotators should not see machine predictions before source-gold labels are frozen. At least one reviewer other than the generator author checks the final labels and split. Disagreements are adjudicated and retained in the QA record.

The current annotation-v2 schema is evidence-aligned and contains no tax-group gold or source-region field. It is not, by itself, a complete source-gold contract. TV2 must propose a versioned additive representation before source-level accuracy is run; do not silently change v2 labels or fabricate source geometry.

### Annotation statuses

| Gold status | Meaning | Scoring treatment |
|---|---|---|
| PRESENT | The source has a readable value | Exact status plus canonical value; positive class for value P/R/F1 |
| NOT_PRESENT | The field/cell is absent from the source | Correct absence counts as exact; a predicted PRESENT value is a false positive |
| UNREADABLE | The field exists, but its value cannot be transcribed reliably | Score status/review handling; no canonical-value target |
| AMBIGUOUS | The source supports multiple unresolved interpretations | Score status/review handling; no forced canonical value |
| UNKNOWN | Annotation is unavailable or not yet adjudicated | Exclude that field/cell from value metrics and report its count/coverage; never treat it as absent |

Machine output is scored from the immutable pre-correction prediction snapshot. A post-review value, acknowledgement, export or verification state is a separate human-workflow result and cannot replace the machine prediction.

## 3. Eligible samples and denominator rules

The source manifest is the authority for the intended cohort. Before execution, every record needs a unique sample ID, file SHA-256, dataset family/snapshot, split, template family, parent/variant link, source route, quality condition, synthetic/public/authorized flag and expected eligibility decision.

1. **Core eligible input:** an in-scope image, born-digital PDF or scanned PDF that passes the published upload policy. Count it from first processing attempt, even if reader, KIE, worker or export fails.
2. **Failure denominator:** a timeout, crash, invalid structured result or no terminal reviewable result is a failed eligible document. Keep stage, code and elapsed time. For complete-header/table/invoice accuracy it scores incorrect; for field P/R/F1 it contributes missing predictions for all labeled cells. Never drop it because the model returned no JSON.
3. **Out of scope:** a file declared before the run as corrupt, encrypted, unsupported or outside size/page limits is reported in a separate challenge table with expected handling. If a supposedly eligible sample is discovered to violate policy only after processing starts, count it as a failure and report why.
4. **Field denominator:** include gold statuses other than UNKNOWN. Report labeled-cell coverage and UNKNOWN count beside every score. A sample with UNKNOWN in a required header or line cell remains in eligible-processing counts but is not eligible for strict complete-invoice scoring. Processing success is determined by the actual terminal outcome, independently of gold coverage.
5. **Document-completion denominators:** complete-header requires adjudicated known labels for all 13 headers only; complete-table requires a complete reviewed row inventory and known labels for all five cells of every gold row; complete-invoice requires both. Report separate scoreable header/table/invoice counts beside the eligible-input count. Missing line gold must not exclude an otherwise scoreable header result, nor vice versa.
6. **No rows:** a labeled invoice with zero line rows is valid only when a source-hash-bound independent review explicitly confirms no line items. An empty annotation array alone does not distinguish confirmed empty from unadjudicated inventory. Record that distinction in the versioned source review/sidecar; unresolved inventory is unscoreable for strict table/invoice accuracy and coverage is reported. A nonempty source whose predictions contain zero rows has zero row recall and fails complete-table accuracy.
7. **Paired comparison:** compare only shared original sample IDs and hashes. A method failure remains in that pair as a failure. Report unmatched/missing paired records; do not quietly compare different cohorts.
8. **Variants:** pages, crops, repeated renders and degradations are nested under a base invoice. Keep all derivatives in the same partition and resample/group by template family, not by derivative image.

## 4. Metric dictionary

For all ratios, a zero denominator is **null**, not zero. Publish numerator, denominator, null count and coverage. Use canonical normalization rules frozen before final extraction.

| Metric | Definition |
|---|---|
| Processing success | Eligible documents reaching the declared terminal structured-output state / eligible documents attempted. Include failures in the denominator. |
| Field exact match | Labeled cells whose predicted status and canonical value exactly equal source gold / cells with gold status other than UNKNOWN. Non-value statuses compare by status with canonical value null. |
| Exact-value extraction precision/recall/F1 | On known labels only: positive means gold status PRESENT and prediction is PRESENT with the exact canonical value. Wrong PRESENT values count as both a false positive and a false negative. Report per field, micro counts and macro over fields with defined denominators. |
| False-value rate | Predicted PRESENT cells on known gold statuses other than PRESENT / predicted PRESENT cells over known gold. Report alongside exact match; do not include UNKNOWN labels. |
| Review rate | Machine cells marked for review / known gold cells. Review rate is not accuracy. |
| Row detection precision | One-to-one matched gold rows / predicted rows. |
| Row detection recall | One-to-one matched gold rows / gold rows. |
| Row detection F1 | Harmonic mean of row precision and recall; report its counts. |
| Extra-row rate | Unmatched predicted rows / predicted rows. |
| Per-column exactness | Exact status + canonical value for a line-item column on matched rows; report denominator, and separately report gold rows left unmatched. |
| Complete-line accuracy | Gold rows whose row is matched and every required, annotated cell is exact / gold rows whose required cell labels are all known. An unmatched gold row is incorrect. |
| Complete-table accuracy | Documents with every gold row/cell exact and no extra predicted row / documents with fully adjudicated row/cell gold. |
| Complete-header accuracy | Documents with all 13 supported header fields exact / documents whose 13 header labels are fully known. |
| Complete-invoice accuracy | Documents with all 13 supported headers and all line rows/cells exact and no extra row / documents with complete adjudicated gold for that scope. Explicitly label scope “13 headers + line items; tax excluded.” |
| CER/WER | Character/word edit distance against a complete, adjudicated transcript, with text normalization policy recorded. Only score pages/regions with transcript coverage. |
| Latency | Record client upload-to-terminal wall time and worker stage durations separately. Report count, failures, p50/p95, cold/warm condition, runtime/model/config identity. Model loading/subprocess startup remains included in the end-to-end total. |
| Human workflow | Time to verified export, final correctness against source gold, value/row edits and unresolved items, computed from the separate reviewed snapshot. Never merge these numbers into machine accuracy. |

For end-to-end row matching, use page plus source-region geometry, independently labeled from the file. Merged PR #69 supplies the *development candidate* `page-bbox-positive-iou-cardinality-1.0`: one-to-one maximum-cardinality matching for strictly positive intersection, without predicted text/value. Its local edge ordering by IoU and prediction index does not guarantee the maximum total IoU assignment or independently established source reading order; see D2 in [TV1 decisions](tv1-evaluation-decisions.md) for the counterexample and adoption options. Tiny-overlap/merged-row failure modes and the original coordinate frame require an explicit development stress review before TV1/TV2 accept or replace this version. Freeze the accepted algorithm/version and any threshold on development data **before** opening the unseen final set. For the aligned KIE evaluator, block-ID overlap is a separate module diagnostic, not source-level row recall.

## 5. Experiment matrix

Each eligible base document belongs to one template partition. Every supported route and degradation variant is recorded in the source manifest; impossible combinations are N/A and are not silently pooled.

| Original route | Seen templates: clean / quality slices | Unseen templates: clean / quality slices | Independent mock | Method comparison |
|---|---|---|---|---|
| JPG/PNG image | Report counts and all defined metrics per quality slice | Same; final stays sealed until freeze | Report separately when mock is image | Characterize OCR pipeline; no route-aware contrast unless paired method exists |
| Born-digital text PDF | Report counts, native-text success/fallback and OCR-all control | Same; final stays sealed | Report separately when available | E1 OCR-all vs route-aware on identical file bytes and fixed downstream KIE |
| Scanned/image-only PDF | Report counts and all defined quality slices | Same; final stays sealed | Report separately when mock is scan PDF | Characterize OCR pipeline; no route-aware contrast unless both modes are run on the same files |

| Experiment | Frozen change | Required evidence |
|---|---|---|
| E1 routing | OCR-all vs direct text/route-aware on the same born-digital PDFs; fixed KIE | Pair IDs/hashes, reader mode/config, accuracy delta, route/fallback/failure, client and worker time |
| E2 grouping | Current row-producing geometry baseline vs one proposed row-producing grouping version; same OCR evidence | Source/aligned gold, row matching, row P/R/F1, per-cell and complete-line/table metrics |
| E3 normalization | Frozen minimal canonical parser vs proposed normalizer; same selected candidate strings and canonical targets | Gain/harm transition counts, false-value introductions; raw transcription and labeled consistency-warning quality reported separately |
| E4 generalization | Seen development/validation vs sealed unseen template families | Family-level scores/counts, strict complete accuracy, failure/error slices |
| E5 robustness | Clean vs predeclared blur/noise/rotation/perspective/scan-like variants | Parent links, transformation parameters/severity, same split as base, paired per-document differences |
| E6 independent challenge | Main generator vs independently authored mock templates/process | Authoring separation, blind QA, sealed hashes, same frozen model/config |
| E7 human pilot | Manual vs assisted review, optional | Supervisor approval, counterbalanced tasks, machine snapshot, separate reviewed output and blind final scorer |

RQ1 and E1 use a paired design. For binary per-document completion, report paired outcomes and a paired method; if a confidence interval is used, resample template families/source invoices, record the seed and interval method. With too few independent template families, show descriptive counts and do not make population-level claims. TV1's current decision is to report the paired accuracy/latency **trade-off**, not a non-inferiority claim: no justified accuracy-loss margin has been set. No threshold, margin or quality cutoff may be selected after revealing the final results; if a later formal claim needs a margin, it must be predeclared, justified, co-signed and versioned before test access.

## 6. Freeze and release gates

| Gate | Owner(s) | Evidence required | Current state (26 Oct 2026) |
|---|---|---|---|
| G1 — Protocol contract | TV1 coordinates; TV2, TV4 and TV5 co-sign | This matrix reviewed; gold layers, statuses, scope, denominator, row matching, failure and tax policy fixed | Draft created in this branch; co-signatures pending |
| G2 — Source dataset QA | TV2 + independent reviewer | Supported original files; complete row inventory; schema/semantic checks; source gold; manifest/hash; family-disjoint split; independent review | PENDING. [PR #66](https://github.com/vietreceipt-team/vietreceipt/pull/66) now supplies 30 base invoices, six layout families, 510 variants and review tooling; automated QA is distinct from independent source/regions/alignment approval. The #60/#61 schema failure is historical, superseded by #66. |
| G3 — Reader/alignment handoff | TV3 + TV2, checked by TV4 | File hashes, real reader evidence, canonical page frame, block/order, source-to-evidence QA and unmatched cases | DEV EVIDENCE ONLY. Updated [PR #65](https://github.com/vietreceipt-team/vietreceipt/pull/65) reports 40 real reads on 20 TV2 v0.2 validation inputs: five parents, one family, four variants each. These replace the older 54-run cohort for current handoff; independent source/alignment review is pending. |
| G4 — Development evaluator | TV4 + TV5, TV1 reviews | Accepted matcher/version; five-state and failure regression; reviewed original-file cohort with full denominators/provenance | PENDING ACCEPTANCE. [PR #69](https://github.com/vietreceipt-team/vietreceipt/pull/69) and [PR #70](https://github.com/vietreceipt-team/vietreceipt/pull/70) are merged in main `07c7cd0`: UNKNOWN/strict denominators, row P/R/F1, source-spatial kernel and source runner exist. [PR #71](https://github.com/vietreceipt-team/vietreceipt/pull/71) adds exact-value/status/row counters and edge tests. Outstanding work: independent source/empty-table QA — [#47, TV2](https://github.com/vietreceipt-team/vietreceipt/issues/47); precise matcher acceptance and development scoring — [#49, TV4](https://github.com/vietreceipt-team/vietreceipt/issues/49); approved original-file execution — [#50, TV5](https://github.com/vietreceipt-team/vietreceipt/issues/50). Block-ID matching remains module-only. |
| G5 — Final freeze and execution | TV1 + TV2; TV3/TV4/TV5 execute without tuning | Locked file/gold hashes, split and config/code commit; sealed final predictions; complete denominator; independent QA signoff | Not passed; no verified, sealed V2 final gold |
| G6 — Product/report acceptance | TV5 + TV6; TV1 signs claims | Success/failure demos, immutable machine snapshot, corrections/export, figures tied to artifacts and declared recovery limits | PARTIAL. Merged #70 has three-route provider evidence; [PR #68](https://github.com/vietreceipt-team/vietreceipt/pull/68) reports four real browser workflows on main `07c7cd0`, with immutable snapshots and parsed exports. This is fictional workflow evidence. Recovery of omitted rows, final report acceptance and any user study remain open. |

No gate is passed by unit-test success, generator output alone, PR merge, or a synthetic smoke test. Only record a gate as passed after its evidence is attached and owner review is explicit.

G4 is blocked by acceptance and reviewed execution, not absence of the already merged metric code. Verify the five gold states and required-UNKNOWN coverage on the accepted evaluator version; compare both methods on one locked mask. Failed eligible inputs remain in source-level denominators. Review the complete source row inventory and D2 matcher stress outcomes before a scored development batch. The current unreviewed source plan must keep failing closed; no QA status or reviewer identity may be filled from software test doubles.

## 7. Result-to-claim traceability

| Research question / claim | Required result | Table/figure | Conclusion rule |
|---|---|---|---|
| RQ1: paired routing trade-off on born-digital PDFs | Same files; complete metrics, failure counts, paired latency and uncertainty | Table 1; Figure 3 paired differences | Report observed differences and scope/uncertainty; D3 makes no accuracy-preservation or non-inferiority claim |
| RQ2: row reconstruction and the pipeline work across layout/quality conditions | Source-gold complete-line/table/invoice metrics; template-family and quality slices; failure cases | Table 2; Figure 1 per-family outcomes; Figure 2 error counts | Describe only named dataset/routes/template families; an unseen drop is reported, not hidden |
| RQ3: assisted review changes human effort without reducing correctness (optional) | Counterbalanced pilot; source-scored final result; separate machine and reviewed snapshots | Table 3; Figure 4 paired participant/task times | If not run, mark “not conducted.” With a tiny pilot, report descriptive results only and make no population-level saving claim |

All result cells stay “not run” until a run artifact is checked. The final report must include sample counts, failures, eligible/scoreable gold counts, config, commit, dataset snapshot and uncertainty next to every score.

## 8. Approval record

| Role | Approval needed | State |
|---|---|---|
| TV1 | Research question, metric and claim protocol | Drafted; final run-owner signoff still pending |
| TV2 | Source-gold representation, labels, split, independent QA and eligibility | Co-sign requested on draft PR #64; pending |
| TV4 | Aligned-gold mapping, row matching and metric implementation | Co-sign requested on draft PR #64; pending |
| TV5 | Source-file runner, machine snapshot and failure/latency fields | Co-sign requested on draft PR #64; pending |
| TV6 | Human-review observations kept distinct from machine metrics | Pending for E7 |

Do not read the sealed test outputs or claim final acceptance until G1–G5 are recorded as approved/passed.


## 9. TV1 decision record and actionable acceptance (24 Oct 2026)

Read [TV1 evaluation decisions](tv1-evaluation-decisions.md) for D1–D6 (exact-value counters; matcher assignment/stress cases; neutral RQ1 comparisons; gold inventory/freeze; optional pilot; same-target normalization and timing). Track required PR evidence and regression test cases in [TV1 acceptance tracker](tv1-acceptance-tracker.md). These are **TV1 policy proposals for cross-owner review**, not substitute signatures or benchmark results. The `UNKNOWN` exclusion and five-state handling must be verified on PR #69/#70 versions. PR #66's development `test` split is not an untouched independent final cohort. G5 remains locked until G1–G4 actually pass. Never report implementation test counts as measured extraction accuracy.
