# TV3 → TV2/TV4: source coordinates and evidence linkage

The Reader wire format remains `document-2.0` with one canonical OCRResult per
page. The audit below checks saved artifacts without running OCR or rewriting
IDs. A passing audit establishes hash/identity/frame consistency; human review
must still establish whether a polygon encloses the intended source text.

## Reproduce the source-frame audit

```sh
python -m scripts.audit_reader_geometry \
  --run-dir results/dev/tv2-reader-v02/paired-20261024 \
  --manifest results/dev/tv2-reader-v02/inputs-20261024/manifest.json \
  --output results/dev/tv2-reader-v02/geometry-20261024
python -m unittest tests.test_audit_reader_geometry -v
```

Use a new output directory for each audit. The command validates the same cohort
as `comparison.json`, reopens each successful run's original input, and checks:

- Input bytes against manifest, paired comparison, handoff and metadata hashes;
  evidence hash and, when present in the handoff, metadata hash.
- Receipt identity and distinct OCR run UUIDs; zero-based contiguous page indexes;
  block IDs unique across the run; contiguous zero-based reading order per page.
- Canonical four-point normalized polygons through the existing contract
  validator, source page count and dimensions, metadata page count and frame.
- Image EXIF display dimensions, PDF crop/unrotated dimensions, intrinsic PDF
  rotation, configured rendering DPI and applied OCR orientation.

`geometry-audit.json` and `pages.csv` preserve source dimensions, effective PDF
crop box, intrinsic rotation, DPI, EXIF information, route/fallback, inverse OCR
rotation and source/evidence/metadata hashes. `blocks.csv` exports text, page,
reading order, exact normalized polygons and their source-frame pixel projection.
The resized/rotated OCR working dimensions are **derived from configuration and
source dimensions**, not a measurement from inside the OCR engine.

Failed reads remain in `expected_runs` and `failures.csv`; they have no invented
blocks or geometry audit. A successful comparison entry without matching evidence
fails the audit. Historical artifact provenance is retained; this post-run audit
does not assign a new inference commit to an old run.

## Coordinate contract

| Input | Canonical polygon frame | Source dimensions |
| --- | --- | --- |
| PNG/JPEG | Top-left, after EXIF display transpose, before OCR orientation/resize | Decoded EXIF-displayed image width/height |
| PDF text | Top-left of effective cropped page, intrinsic rotation reset to 0 | `ceil(page_width_pt × DPI/72)`, likewise height |
| PDF scan / OCR-all | Same crop/unrotated frame as PDF text | Rendered RGB page dimensions at configured DPI |

Each polygon contains normalized `(x,y)` in `[0,1]`, ordered TL/TR/BR/BL in image
space. For a source preview of size `W × H`, use `(x×W, y×H)`. Do not scale an
already normalized polygon again for `max_side`. Raster rounding can introduce
subpixel differences between PDF points and the pixel projection; normalized
coordinates are the linkage representation.

PDF text glyph boxes originate in PDF bottom-left coordinates. For effective
crop box `(left,bottom,right,top)`, Reader normalizes as
`x=(glyph_x-left)/(right-left)` and `y=(top-glyph_y)/(top-bottom)`. The viewer must
use that same cropped page with rotation 0. To draw in an intrinsically rotated
viewer or another crop frame, explicitly transform both gold and evidence first;
do not reuse these polygons unchanged.

Image EXIF transforms may rotate **or reflect** stored pixels. Source gold for
raw, untransposed pixels must undergo the same EXIF display transformation before
comparison. The audit records the original EXIF orientation and both raw/display
dimensions. It does not invent the gold transformation or approve an external
annotation's coordinate frame.

For OCR, Reader preserves aspect ratio during thumbnail resize, applies its
clockwise orientation correction, then maps normalized OCR coordinates back:

| Applied clockwise correction | OCR `(x,y)` → canonical source `(x,y)` |
| --- | --- |
| 0° | `(x,y)` |
| 90° | `(y,1-x)` |
| 180° | `(1-x,1-y)` |
| 270° | `(1-y,x)` |

Polygons are reordered into the canonical corner order after this mapping.
Reading order is the Reader's upright OCR row-major sequence; it is an explicit
ordinal, not a promise that blocks reconstruct semantic table rows. The audit
checks ordinal consistency, not human reading correctness. Perspective/skew
already present in source bytes stays part of the source frame; Reader does not
claim to undo it.

## TV2/TV4 handoff and acceptance

1. Select a manifest variant by immutable input SHA-256. Read its handoff entry,
   `receipt_id`, mode and **exact `ocr_run_id`**. One parent receipt can have many
   input variants and two route runs; block IDs alone do not identify a run.
2. Review source gold/regions against the source file independently of OCR/KIE.
   Declare the source page/crop/EXIF frame explicitly and retain source/gold/region
   hashes, reviewer, review time and unresolved disagreements.
3. For aligned KIE gold, link `page_index` (zero-based) plus `source_block_ids`
   from that exact evidence run. Review both modes independently. Never copy
   block IDs from a prior run or infer an absent field from an OCR omission.
4. Keep source-visible text/fields in source gold when OCR omits them; retain
   unmatched/unresolved alignment with the source reason. Do not edit raw OCR or
   silently change source gold to agree with recognition.
5. TV4 validates the aligned input and checks its 13 headers and 5 cells per row
   under the agreed protocol. Source-gold scoring and aligned KIE-only scoring
   are different experiments. Until actual independent QA and protocol approval,
   output remains development diagnostics and KIE accuracy stays unscored.

For visual review, run `scripts.demo_document_reader` with the **saved evidence**
and matching original source. Its preview uses image EXIF transpose and PDF
rotation 0; inspect glyphs, table neighbors, all pages and any rotated/cropped
cases. Record a review against artifact hashes. Contract tests and a generated
overlay do not constitute independent human annotation approval.

The focused audit tests use an explicit fake OCR provider with real image/PDF
decoding. They cover EXIF rotation + resize + inverse OCR rotation, a cropped
90-degree two-page PDF, frame/page/hash drift, missing evidence and retained
failures. They are geometry regressions, not OCR accuracy measurements.
