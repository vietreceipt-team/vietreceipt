# TV1 — Defense and demonstration playbook

**Date:** 2026-10-24. **Status:** prepared script; execution must be documented by TV5/TV6. This file does not certify that a demo or user study was conducted.

## Defense structure (12–15 minutes, adapt to university allocation)

| Slide | Content | Show | Timing guide |
|---|---|---|---|
| 1 | Problem, scope and user need | Three supported document routes | 1 min |
| 2 | Why simple OCR/KIE is insufficient | Wrong row association illustration | 1 min |
| 3 | Related work and limits | CORD/SROIE/LayoutLMv3/Donut compared by task | 1 min |
| 4 | RQ1–RQ3 and contributions | Implemented vs experimentally tested distinction | 1 min |
| 5 | System architecture | Reader -> evidence -> KIE -> review/export | 1.5 min |
| 6 | Canonical contracts | 13 header fields, five line-item cells, five statuses | 1 min |
| 7 | Dataset and validity | Public vs synthetic vs independent mock; source/aligned gold | 1.5 min |
| 8 | Experimental setup | E1 route A/B, E2 row A/B, E4–E6 | 1.5 min |
| 9 | Results | Only genuine tables with n, failures, split and hash | 2 min |
| 10 | Demo success and real correction | Live three-format source-backed flow | 2 min |
| 11 | Failure modes and limitations | Wrong row, OCR miss, ARM64/runtime | 1 min |
| 12 | Conclusions and future work | Evidence-bounded contribution statement | 1 min |

If experiments are not completed, slide 9 must be titled **“Evaluation readiness and remaining work”**, not fabricate achieved scores. Do not confuse a framework designed to score with a scored benchmark.

## Live demo checklist

**Requirements:** dedicated test environment, fictional local sample inputs, real Document Reader + KIE providers (not mock test providers), API and worker up, PostgreSQL/Redis reachable, deterministic export and recording of version/commit. TV5 guide: [reproducible demo](v2-reproducible-demo.md). Known Linux ARM64 Paddle OCR crash remains possible; the repository's AMD64 worker overlay is a documented compatible option on tested ARM64 Docker systems, not a guarantee.

### Case A — born-digital PDF
1. Show source text PDF, import/upload, processing status and route evidence.
2. Display extracted 13 header slots and every detected item row alongside highlighted source.
3. Call out missing/unreadable/ambiguous flags honestly; choose at least one real incorrect machine value if this input exposes one.
4. Correct value or row in UI; verify; export JSON, CSV and XLSX if supported by the build.
5. Fetch immutable machine snapshot again and demonstrate it is not overwritten by the reviewed value.

### Case B — image JPG/PNG
1. Import independently labeled fictional image with readable and problematic regions.
2. Show OCR blocks, source highlighting and field/row links, not only final totals.
3. Show one source-linked mistake or explicitly state if this sample did not exhibit one.
4. Correct/verify/export if available; record any unsupported behavior as a demo failure.

### Case C — scanned PDF
1. Upload scanned PDF with no usable native text layer.
2. Show documented OCR path and timing.
3. Show correction workflow including item-row grouping where sample supports it.
4. Retain errors and failures in the trial log.

### Case D — controlled failure
Use a predeclared harmless, unsupported or corrupted **synthetic** document, or an engineering-recorded actual Reader failure. Show terminal FAILED, message/state and preserved evidence/provenance. The failed document must not vanish from eligible processing outcomes if it was in-scope. Do not deliberately destabilize production or use user private invoices.

## Demo acceptance record

| Field | Fill after executing, not ahead of time |
|---|---|
| Date, runner, reviewer | NOT RUN |
| Environment, OS/architecture, Python/model versions | NOT RECORDED |
| App/backend/worker commits and configuration | NOT RECORDED |
| Source hashes and sample IDs, synthetic flag | NOT RECORDED |
| Actual route used and fallback | NOT RECORDED |
| Successful API/worker processing per format | NOT CONFIRMED THIS SESSION |
| Source highlight and row correction | NOT CONFIRMED THIS SESSION |
| Unmodified machine snapshot after correction | NOT CONFIRMED THIS SESSION |
| Verify and export format validation | NOT CONFIRMED THIS SESSION |
| Failure case and preserved error stage | NOT CONFIRMED THIS SESSION |
| Console/CI/screen-recording or run artifact links | NOT RECORDED |

Do not mark any row PASS based on tests from an earlier commit. CI with fake providers is not a real-provider demo.

## Frequently asked defense questions

**Q: What is novel if the project does not train a new OCR model?**  
A: The work studies document-route choice, semantically structured line-item recovery and evidence-linked human verification as one measurable workflow. Novelty must be defended by controlled evaluations, not by claiming an unimplemented neural architecture.

**Q: Why not just use OCR accuracy?**  
A: Correct tokens can still be assigned to the wrong seller/total/product row. End-to-end canonical headers and complete-line/table/invoice outcomes test semantic correctness beyond CER/WER.

**Q: Why exclude tax breakdown from complete invoice?**  
A: The versioned gold used for those strict metrics only supports 13 canonical headers and line-item cells. Tax groups can exist in product output but cannot ethically be treated as evaluated without matching independently reviewed labels.

**Q: Why synthetic and public data?**  
A: They permit controlled input diversity, reproducibility and privacy-safe demos. The weakness is limited external validity; independent mock templates and, later, authorized real invoices are needed for stronger claims.

**Q: Why compare route-aware with OCR-all only on text PDFs?**  
A: Both methods are valid on the identical original born-digital PDF. Image/scan inputs cannot demonstrate the gain from direct reading a native text layer. We report those routes separately.

**Q: What are the remaining constraints?**  
A: Independent source gold and final split readiness, limited annotated layout diversity, source geometry and grouping edge cases, runtime/platform variability, and no completed study to infer human time savings.

**Q: Why is UNKNOWN excluded?**  
A: It indicates annotation unavailable, not source absence. Treating it as “correctly unknown” would reward missing gold and inflate accuracy. The number of excluded fields/documents is always reported.

**Q: How do you prevent a misleading accuracy result?**  
A: Original-file source-gold scoring; immutable predictions; independent QA; explicit eligibility/failed cases; fixed version/config; template/parent-disjoint splits; no post-test tuning and linked artifacts.

**Q: Can we claim a specific grade?**  
A: No. Presentation quality and engineering/testing readiness can be improved, but no score can be guaranteed.
