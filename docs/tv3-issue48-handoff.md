# TV3 — Issue #48: OCR / PDF comparison and evidence handoff

Prepared locally on 23/10/2026, Asia/Saigon. Scope: issue [#48](https://github.com/vietreceipt-team/vietreceipt/issues/48)
and its 23/10 comment, following [#59](https://github.com/vietreceipt-team/vietreceipt/issues/59).
Reader V2 from PR #55 is reused. This records the original local inference run;
its source/evidence is now published with the TV3 follow-up PR. Teammate comments
remain a separate human handoff.

## Inputs and provenance

At inference time the workspace was a source archive without `.git`. Run configuration
therefore records `git_commit: unavailable` and SHA-256 of the actual Python
sources rather than inventing a local commit. GitHub main inspected on 23/10 was
`061960f0e38549f27b3183ebc3008c58ef0e5570`; that is remote context, not a claim
that the modified archive has that commit. Before publishing later, apply/review
the local changes on a real Git checkout. Git has since been restored and the
publication branch synchronized with main; original run provenance remains immutable.

The [historical diagnostic ZIP](../results/dev/document-reader-v2/tv3-diagnostics-20261023.zip)
contains the inputs, raw runs and source snapshots for the earlier experiment.
The [TV2 follow-up ZIP](../results/dev/tv2-reader-v0/tv3-tv2-handoff-20261023.zip)
contains the later validation experiment. Extract at a project root to resolve
manifest/handoff paths. Selected reports and overlays are also tracked directly.

The earlier inspection of PR #60 at `c3d04d1679bf246f6e1cc253fd58c8e3d5675913`
was SVG-only. The later head `5e5b871dd1c7413f2d74acc175aad0f0186486f7`
includes PNG, vector PDF and degraded image-only PDF variants. A selected TV2
validation subset is now imported locally; see the [TV2 follow-up](tv3-tv2-synthetic-v0.md)
for source hashes, the explicit LF/CRLF transfer ledger and the real Reader run.
It remains a draft development dataset with incomplete/unaligned KIE labels.
PR #61 QA tooling was draft at `3d0e955b23b9acec68b1310c6e2679bdba9463b8`
when originally inspected; it is not silently merged into this work. The earlier
local fixture family below remains a separate fictional one-template diagnostic.

## Reproduce the experiment

Use pinned Python 3.12 dependencies in `requirements-document-reader.txt` and
`requirements-document-reader-test.txt`. This machine retains a working runtime at
`C:/Users/ADMIN/Downloads/vietreceipt_ocr_probe/.venv/Scripts/python.exe`.
The model cache for these runs is the current workspace's `.paddlex-cache`.

```powershell
python -m scripts.create_document_fixtures --output results/dev/document-reader-v2/local-fixtures-20261023 --font C:/Windows/Fonts/arial.ttf
python -m scripts.compare_pdf_routes --manifest results/dev/document-reader-v2/local-fixtures-20261023/manifest.json --output results/dev/document-reader-v2/local-paired-native-20261023 --orientation auto
```

Use a new output directory for every run. Both modes use the same source files
and config except `force_pdf_ocr`. Keep all failures. CER/WER collapse whitespace
only and retain Vietnamese accents/case. `char_deletions` measures deletions in
the optimal character alignment, not a semantic missing-field count.

Generated inputs: text PDF, clean PNG, JPEG, blur, 7-degree tilt, noise,
perspective, scan PDF, two-page text PDF, two-page scan PDF, mixed two-page PDF,
90/180/270-degree image rotation, corrupt PDF. Corrupt PDF has an expected typed
failure and no reference text. Source transcriptions are diagnostics, not an
oracle-text score presented as real OCR.

## TV2 / TV4 handoff contract

Open `handoff.json`, select a sample/mode and load its `evidence_path` relative to
the run directory. Each strict document envelope contains:

- `receipt_id`, `ocr_run_id`, `schema_version: document-2.0`;
- zero-based `page_index`;
- exact block `block_id`, `text`, `polygon`, `reading_order` inside `page.evidence`.

IDs are unique inside a run; the durable reference is
`(receipt_id, ocr_run_id, page_index, block_id)`. A block ID by itself is not a
cross-run identity. The two comparison modes have separate run IDs and can have
different segmentation. Do not reuse alignment IDs between modes.

TV2 must keep source gold independent of OCR, then align gold to the **actual**
selected evidence run and QA it. Do not synthesize placeholder block IDs, infer
ground-truth absence from OCR omissions, or copy OCR predictions into gold.
TV4 can pass the envelope directly to `ai.kie.v2.extract_invoice` without ID
rewriting. Provider/schema acceptance does not establish extraction accuracy.

## Coordinate transformations and confidence

Polygons are normalized top-left coordinates, in TL/TR/BR/BL order.

| Input | Coordinate frame |
| --- | --- |
| PNG/JPEG | Display orientation after EXIF, before OCR rotation/resize |
| PDF text | Crop box, unrotated PDF.js viewport (`rotation=0`) |
| PDF OCR | Same crop/unrotated frame, RGB PDFium render at configured DPI |

PDF's intrinsic page rotation is recorded and reset to 0 for both extraction and
rendering. Pixel dimensions are `ceil(page_points * dpi / 72)`. Aspect-preserving
resize keeps normalized coordinates. For OCR clockwise correction angle `a`,
the normalized OCR point `(x,y)` is restored to source as follows:

| a | Source x | Source y |
| --- | --- | --- |
| 0 | x | y |
| 90 | y | 1-x |
| 180 | 1-x | 1-y |
| 270 | 1-y | x |

Points are then ordered/clamped to the source frame. Evidence is ordered using
overlapping baselines and left-to-right position in the OCR reading frame;
this does not reconstruct semantic table rows. All transformations/configuration
are carried in the metadata sidecar, without changing the strict wire envelope.

PDF direct text retains numeric confidence `1.0` only for transport compatibility.
Its confidence is **N/A**, not 100% correctness. OCR engine confidence is an
uncalibrated engine score; neither value is a KIE field confidence.

## Runtime profiles and remaining acceptance

The native Windows CPU run is a Reader/KIE provider check, not a full frontend /
queue / database demo. Paddle's first use also needs its auxiliary font; prewarm
models and fonts on the demo machine. Preserve the first restricted run log,
which shows initialization failure, separately from the native rerun.

Docker CLI is absent on this machine. Docker smoke and a native-vs-Docker timing
comparison cannot be claimed here. Existing `docs/backend-v2-integration.md`
reports text-PDF success on Docker Desktop ARM64 and native Paddle SIGSEGV for
image/scan in Linux ARM64, even with one OpenMP thread. Changing Celery's pool
does not establish a fix. The reported native macOS worker is historical
evidence; this delivery adds a separate Windows native check. Keep ARM64
image/scan support explicitly unverified until a real smoke succeeds.

Still requires team input:

1. TV2 has delivered rendered development inputs. Independently reviewed source
   transcriptions and corrected source gold are still required; keep final test locked.
2. The [TV2 follow-up](tv3-tv2-synthetic-v0.md) records the selected validation run,
   overlays and representative errors. Expand only on eligible development inputs.
3. TV2 independently QA-aligns source gold to the chosen run; TV4 confirms its
   evaluator consumes those IDs. This has not happened merely because KIE runs.
4. TV5 verifies the deployment's actual CPU/OS architecture and end-to-end demo.

These dependencies prevent marking the entire GitHub issue DONE. The local
scripts, diagnostic results and evidence package are deliverable now.
