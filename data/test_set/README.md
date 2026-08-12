# Frozen Week-1 OCR test set

This directory contains the fixed test set selected before running any OCR engine.

## Composition

- `standard_mixed_layout`: 20
- `challenge_low_contrast`: 5
- `challenge_low_sharpness_or_distance`: 5
- `challenge_lighting_or_perspective`: 5
- `challenge_long_receipt`: 5

The metric-based strata are sampling aids, not audited semantic labels. Manual merchant and quality labels remain blank in `test_manifest.csv` until reviewed.

Do not replace images after observing OCR outputs. If the set must change, create a new version and document the reason.
