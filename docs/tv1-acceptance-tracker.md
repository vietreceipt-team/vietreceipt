# TV1 acceptance tracker and handoff checklist

**Snapshot checked via GitHub API:** 2026-10-24 (Asia/Bangkok). **Maintainer:** TV1. This is an evidence register, **not approval** for any other member, a live CI monitor or a final benchmark.

This file operationalizes the [Evaluation matrix](evaluation-matrix.md) and the [TV1 decisions](tv1-evaluation-decisions.md). Replace a PENDING state with PASS **only** after an actual linked artifact and the relevant human review are recorded.

## 1. Current branches / avoid duplicated tasks

| Source | What exists on the branch | What is *not* established |
|---|---|---|
| [PR #64](https://github.com/vietreceipt-team/vietreceipt/pull/64) — TV1 | RQ1–RQ3 matrix, user pilot protocol, research design; TV1 decision record and this tracker | Reviewers' explicit co-sign, executable final evidence; PR remains draft |
| [PR #66](https://github.com/vietreceipt-team/vietreceipt/pull/66) — TV2 | Generator and dataset tooling for canonical 13 headers, line items, supported inputs, manifest/QA checks; 30 base synthetic, 510 variants claimed in PR | Verified, independently adjudicated final source gold; generator-derived `test` is NOT final |
| [PR #65](https://github.com/vietreceipt-team/vietreceipt/pull/65) — TV3 | Reader/PDF development handoff, reported 54/54 read tests | Generalization or independently verified accuracy |
| [PR #69](https://github.com/vietreceipt-team/vietreceipt/pull/69) — TV4 | Proposed value-aware metrics, UNKNOWN mask, row P/R/F1, source-spatial kernel; paired development A/B | QA-approved matcher policy, reviewed gold, scored improvement |
| [PR #70](https://github.com/vietreceipt-team/vietreceipt/pull/70) — TV5 | Proposed original-file source runner, immutable machine provenance, fail-closed plan gate; reported candidate plan `PENDING_REVIEW` | Approval of gold/plan, scored run or final accuracy |
| [PR #67](https://github.com/vietreceipt-team/vietreceipt/pull/67) — TV5 | Previously merged capture/evaluation handoff | Source-gold benchmark or human study |
| Issues [#47](https://github.com/vietreceipt-team/vietreceipt/issues/47)–[#52](https://github.com/vietreceipt-team/vietreceipt/issues/52), [#59](https://github.com/vietreceipt-team/vietreceipt/issues/59) | Task ownership and dependencies | Completion from a PR description alone |

The PR test totals and sample counts above are **author-reported evidence**, not tests independently rerun by TV1. If a PR has been merged, rebased or amended since this snapshot, verify the newer source commit before changing gate status.

## 2. Gate decisions (TV1 cannot award an unsigned PASS)

| Gate | Status 24 Oct | Owner / reviewer | Required pass evidence |
|---|---|---|---|
| G1 — Protocol co-sign | **PENDING** | TV1 with TV2, TV4, TV5 | Signed review/comments identifying version and agreement on D1–D4; conflicts resolved in versioned text |
| G2 — Dataset integrity | **PENDING** | TV2 + independent reviewer, TV1 checks | Original supported files, known gold 13+rows/regions, gold/source SHA, independent QA/adjudication, parent+template disjoint split, QA report; no unreviewed final |
| G3 — Reader/evidence handoff | **DEV EVIDENCE ONLY** | TV3 + TV2, TV4 checks | At least image, born-digital PDF and scan-PDF original files; real reader metadata, page geometry, route/reason, source hash, alignments/unmatched cases, failed read examples |
| G4 — E2E metrics and regression | **PENDING** | TV4 + TV5, TV1 reviews | Five-state regression, source-region one-to-one matching stress cases, source identity/coordinate QA, original-file *dev* batch with null/coverage/failure counts and stable artifact hashes |
| G5 — Independent final evaluation | **LOCKED** | TV1 + TV2 + TV4 + TV5 | PASS G1–G4; independent source author/reviewer, frozen matching threshold/code/runtime and file hashes; approved final inventory; sealed primary run |
| G6 — Product/demo/report | **PARTIAL** | TV5 + TV6, TV1 signs conclusions | Real-provider upload → machine-only snapshot → user corrections → verify → export on supported routes, one honest failure case, figures traceable to measured artifacts |

For each PASS, write in the issue or PR: **gate, decision, dataset/sample count, reviewer, source and code SHA, test command, CI/run links, date, known limitations**. Do not change a gate by editing a standalone boolean or test double.

## 3. Contract conformance tests to request of TV4/TV5

All scenarios must run against **the implementation version being accepted**, not only reference pseudocode. Per-field numerator/denominator and per-original outcomes should be asserted.

| ID | Gold / candidate | Expected |
|---|---|---|
| M01 | Gold PRESENT `100`, predicted PRESENT `100` | value TP=1 |
| M02 | Gold PRESENT `100`, predicted PRESENT `200` | TP=0, FP=1, FN=1 |
| M03 | Gold PRESENT `100`, missing output | FN=1; processing failure tracked if applicable |
| M04 | Gold NOT_PRESENT, predicted PRESENT `100` | FP=1, wrong status |
| M05 | Gold NOT_PRESENT, predicted NOT_PRESENT | exact state match; not value TP |
| M06 | Gold UNKNOWN, predicted UNKNOWN or PRESENT | excluded from accuracy; UNKNOWN count increases, never TP |
| M07 | Gold UNREADABLE / AMBIGUOUS | known status-only comparison; no invented transcript; report separately |
| M08 | Required gold UNKNOWN and otherwise correct full invoice | strict document **unscoreable**; eligible attempted count unchanged |
| M09 | Scoreable original fails reader / worker / timeout | strict completion incorrect; failure retained in intended cohort |
| R01 | Two gold rows, one predicted merged box touching both | at most one spatial match (one-to-one), other row FN |
| R02 | Identical row values assigned to the wrong gold row | spatial matching remains value-blind, incorrect cell/line counted |
| R03 | Row boxes on different pages or zero positive overlap | no source-level match |
| R04 | Adjacent boxes with tiny positive overlap | positive-IoU candidate exposes possible false match; TV4/TV1 adjudicate dev-only sensitivity before freeze |
| R05 | Two gold rows, no predictions | recall=0 if gold rows>0; strict complete-table false |
| R06 | Zero gold rows, zero predicted rows with explicit empty gold | complete table true; 0/0 row P/R/F1 = null |
| R07 | OCR block IDs happen to match but source page regions do not | source-level match must remain false |
| R08 | Wrong source hash, EXIF/PDF coordinate frame or reader run | TV5 fail-closed; no partial, misleading accuracy |
| F01 | Missing unreviewed source plan | exit nonzero/QA blocked, `metrics=null`, `evaluated=0`, no HTTP uploads |
| F02 | Mixed approved and unapproved source samples | refuse full scored cohort; do not select only easy approved samples |
| F03 | Reviewer-modified final values equal gold, uncorrected machine output wrong | machine accuracy stays wrong; reviewed accuracy reported separately |
| F04 | Five degradations of one original | same split/parent; not five independent originals for uncertainty analysis |

**Do not claim all tests pass from this table.** TV4/TV5 must attach commands/logs, versions and failures.

## 4. Exact handoff requests by role

**TV2:** In PR #66, provide a read-only audited sample gallery across image/text-PDF/scan-PDF; versioned original Source Gold and row regions; reviewer who is **not sole author**; QA disagreement log; hashes; anti-leak parent/family split. Explicitly label any development `test` records as final-ineligible. Supply a truly independently authored/mock final plan later.

**TV3:** In PR #65/#48, confirm original-file route decisions, geometry frame, raw OCR evidence IDs and source hashes; submit OCR-all vs route-aware paired dev capture (when both are feasible) and failure cases. OCR confidence must not be called calibrated probability without validation.

**TV4:** In PR #69/#49, link five-state/row regression results against D1, positive-IoU sensitivity failures against D2, proposed matcher version, comparable baseline/variant dev output on fixed evidence. Keep grouping variant opt-in until signed comparison.

**TV5:** In PR #70/#50, demonstrate candidate source plan failing closed and, after independent development QA, one command that scores real original files with immutable machine output, failure coverage, source SHA, runtime fingerprints, per-original JSON/CSV. Never infer reviewer signatures from test fixtures.

**TV6:** In #51, prove source highlight, correction, verify/export through real provider on multiple routes; demonstrate machine snapshot remains immutable; pilot optional and only after approval.

**TV1:** Review contributions against G1–G6; collect real co-sign; lock supported configuration and final split **only after** G1–G4; maintain result-to-claim traceability and thesis manuscript. Do not infer agreement from requested reviews.

## 5. Freeze record (copy only when ready)

| Field | Verified value |
|---|---|
| Protocol document commit and D1–D4 approval links | PENDING |
| Original source manifest SHA256 / sample IDs / dataset version | PENDING |
| Independent reviewer, QA/adjudication artifact URL | PENDING |
| Family/parent leakage audit URL | PENDING |
| Source-level matcher identifier and accepted stress report | PENDING |
| Reader, KIE, backend and evaluator commit/config fingerprints | PENDING |
| Approved final eligibility/manifest inventory | PENDING |
| Date/time of seal, owner authorization | PENDING |
| Primary final run ID, raw machine result and failure manifest | NOT RUN |

**Decision on 24 Oct 2026:** *Protocol artifacts advanced; G1–G4 NOT certified; G5 remains LOCKED.* Proceed with development-only review, QA and experiments, not final claims.
