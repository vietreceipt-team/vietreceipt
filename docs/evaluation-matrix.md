# VietReceipt evaluation matrix

**Protocol status:** proposed, not yet co-signed by TV2, TV4 and TV5. This file defines what must be agreed before a final run; it is not a result report. No accuracy values are available from this protocol.

## 1. Research questions and claim boundaries

| ID | Research question | Experiment | Primary outcome | Planned report artifact | Result/status |
|---|---|---|---|---|---|
| RQ1 | On the same born-digital PDFs, does route-aware reading preserve end-to-end correctness while reducing processing time compared with rasterize-and-OCR-all? | E1 paired OCR-all vs direct-PDF-text routing | Paired complete-invoice correctness difference; terminal latency difference; failure difference | Table 1: paired method outcomes and route/fallback counts | Not run; no frozen source-gold manifest |
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
4. **Field denominator:** include gold statuses other than UNKNOWN. Report labeled-cell coverage and UNKNOWN count beside every score. A sample with UNKNOWN in a required header or line cell remains in processing-success counts but is not eligible for strict complete-invoice scoring.
5. **Document-completion denominator:** only documents with adjudicated labels for every required header and line cell can be scored for strict complete-header/invoice accuracy. Show both the number of eligible input documents and the smaller number with fully scoreable gold.
6. **No rows:** a labeled invoice with zero line rows is valid only when source gold explicitly says no line items. A nonempty source whose predictions contain zero rows has zero row recall and fails complete-table accuracy.
7. **Paired comparison:** compare only shared original sample IDs and hashes. A method failure remains in that pair as a failure. Report unmatched/missing paired records; do not quietly compare different cohorts.
8. **Variants:** pages, crops, repeated renders and degradations are nested under a base invoice. Keep all derivatives in the same partition and resample/group by template family, not by derivative image.

## 4. Metric dictionary

For all ratios, a zero denominator is **null**, not zero. Publish numerator, denominator, null count and coverage. Use canonical normalization rules frozen before final extraction.

| Metric | Definition |
|---|---|
| Processing success | Eligible documents reaching the declared terminal structured-output state / eligible documents attempted. Include failures in the denominator. |
| Field exact match | Labeled cells whose predicted status and canonical value exactly equal source gold / cells with gold status other than UNKNOWN. Non-value statuses compare by status with canonical value null. |
| Presence precision/recall/F1 | On known labels only: positive means gold status PRESENT and prediction is PRESENT with the exact canonical value. Wrong PRESENT values count as both a false positive and a false negative. Report per field, micro counts and macro over fields with defined denominators. |
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

For end-to-end row matching, use page plus source-region geometry, independently labeled from the file. Match rows one-to-one by maximum-cardinality positive spatial overlap; use overlap and source reading order only to break ties, never predicted text/value. Freeze the coordinate system and matching rule using development data before opening the unseen final set. For the aligned KIE evaluator, block-ID overlap may be reported as a separate module diagnostic; do not describe it as source-level row recall.

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
| E3 normalization | Raw candidate vs canonical normalized output and warnings; same candidates/evidence | Raw and normalized exactness, false normalization count, warning counts; checks must not rewrite totals |
| E4 generalization | Seen development/validation vs sealed unseen template families | Family-level scores/counts, strict complete accuracy, failure/error slices |
| E5 robustness | Clean vs predeclared blur/noise/rotation/perspective/scan-like variants | Parent links, transformation parameters/severity, same split as base, paired per-document differences |
| E6 independent challenge | Main generator vs independently authored mock templates/process | Authoring separation, blind QA, sealed hashes, same frozen model/config |
| E7 human pilot | Manual vs assisted review, optional | Supervisor approval, counterbalanced tasks, machine snapshot, separate reviewed output and blind final scorer |

RQ1 and E1 use a paired design. For binary per-document completion, report paired outcomes and a paired method; if a confidence interval is used, resample template families/source invoices, record the seed and interval method. With too few independent template families, show descriptive counts and do not make population-level claims. No threshold, non-inferiority margin or quality cutoff may be selected after revealing the final results; record any needed decision margin in the signed protocol beforehand.

## 6. Freeze and release gates

| Gate | Owner(s) | Evidence required | Current state (23 Oct 2026) |
|---|---|---|---|
| G1 — Protocol contract | TV1 coordinates; TV2, TV4 and TV5 co-sign | This matrix reviewed; gold layers, statuses, scope, denominator, row matching, failure and tax policy fixed | Draft created in this branch; co-signatures pending |
| G2 — Source dataset QA | TV2 + independent reviewer | Generator output rendered to upload-supported routes; schema/semantic checks; source gold; manifest/hash; family-disjoint split; independent sample review | Not passed. TV1 review 23 Oct: [PR #60](https://github.com/vietreceipt-team/vietreceipt/pull/60) produced 30 SVGs; running the [PR #61](https://github.com/vietreceipt-team/vietreceipt/pull/61) validator rejected all 30 for header-schema mismatch and warned that SVG is unsupported and evidence IDs are empty. The validator's four unit tests pass, but generated data does not pass its QA gate. |
| G3 — Reader/alignment handoff | TV3 + TV2, checked by TV4 | Original-file hashes; real reader evidence; block/page/polygon/order; source-to-evidence mapping QA; explicit unmatched cases | Pending real, reviewed alignment artifacts |
| G4 — Development evaluator | TV4 + TV5, TV1 reviews | Same OCR evidence for KIE comparisons; original bytes through real reader/KIE for source evaluation; failure rows retained; metrics/version/config/logs; UNKNOWN excluded from value denominators | **Not passed.** Three P0 implementation gaps are tracked: UNKNOWN scoring/complete-metric eligibility and fail-closed regression coverage — [issue #49, TV4](https://github.com/vietreceipt-team/vietreceipt/issues/49); row detection precision/F1 plus tests — [issue #49, TV4](https://github.com/vietreceipt-team/vietreceipt/issues/49); source-region gold and source-level spatial row matching from original files — [issue #47, TV2](https://github.com/vietreceipt-team/vietreceipt/issues/47), [issue #49, TV4](https://github.com/vietreceipt-team/vietreceipt/issues/49), and [issue #50, TV5](https://github.com/vietreceipt-team/vietreceipt/issues/50). Block-ID overlap remains a KIE-aligned diagnostic only. |
| G5 — Final freeze and execution | TV1 + TV2; TV3/TV4/TV5 execute without tuning | Locked file/gold hashes, split and config/code commit; sealed final predictions; complete denominator; independent QA signoff | Not passed; no verified, sealed V2 final gold |
| G6 — Product/report acceptance | TV5 + TV6; TV1 signs claims | Success and failure demos; machine/review snapshots separate; correction/verify/export; tables, error cases and limits trace to artifacts | PR #62 documents a one-template synthetic three-route workflow; omitted-row UX, browser acceptance here and thesis accuracy remain open |

No gate is passed by unit-test success, generator output alone, PR merge, or a synthetic smoke test. Only record a gate as passed after its evidence is attached and owner review is explicit.

G4 stays blocked until the linked owners deliver and test all three gaps. For UNKNOWN, test PRESENT, NOT_PRESENT, UNREADABLE, AMBIGUOUS and UNKNOWN separately; UNKNOWN must not enter value denominators, and final manifests with UNKNOWN in required cells must either fail closed or exclude affected documents from strict complete metrics while reporting eligible and scoreable counts. Row detection precision/F1 must be emitted with counts and zero-denominator behavior. Source-level row matching must use independently annotated source regions and a frozen spatial rule on the original-file end-to-end path; `source_block_ids` intersection is not a substitute for that result.

## 7. Result-to-claim traceability

| Research question / claim | Required result | Table/figure | Conclusion rule |
|---|---|---|---|
| RQ1: route-aware is an acceptable and faster option for born-digital PDFs | Same files; complete metrics, failure counts, paired latency and uncertainty | Table 1; Figure 3 paired differences | Claim only if predeclared accuracy condition and time result both pass; otherwise report the observed tradeoff or reject H1 |
| RQ2: row reconstruction and the pipeline work across layout/quality conditions | Source-gold complete-line/table/invoice metrics; template-family and quality slices; failure cases | Table 2; Figure 1 per-family outcomes; Figure 2 error counts | Describe only named dataset/routes/template families; an unseen drop is reported, not hidden |
| RQ3: assisted review changes human effort without reducing correctness (optional) | Counterbalanced pilot; source-scored final result; separate machine and reviewed snapshots | Table 3; Figure 4 paired participant/task times | If not run, mark “not conducted.” With a tiny pilot, report descriptive results only and make no population-level saving claim |

All result cells stay “not run” until a run artifact is checked. The final report must include sample counts, failures, eligible/scoreable gold counts, config, commit, dataset snapshot and uncertainty next to every score.

## 8. Approval record

| Role | Approval needed | State |
|---|---|---|
| TV1 | Research question, metric and claim protocol | Drafted; final run-owner signoff still pending |
| TV2 | Source-gold representation, labels, split, independent QA and eligibility | Pending |
| TV4 | Aligned-gold mapping, row matching and metric implementation | Pending |
| TV5 | Source-file runner, machine snapshot and failure/latency fields | Pending |
| TV6 | Human-review observations kept distinct from machine metrics | Pending for E7 |

Do not read the sealed test outputs or claim final acceptance until G1–G5 are recorded as approved/passed.
