# Public records kept outside the mapped dataset

These reports identify every rejected native record in the pinned local audit.
Each JSON/CSV includes the original ID, native split, source line, snapshot,
mapping version, reason, retained image hash and native-record hash.
No rejected record was relabeled, rounded or silently dropped.

| Source audit scope | Native records | Mapped | Quarantined | Images/native labels retained |
| --- | ---: | ---: | ---: | ---: |
| Vietnamese Bill, pinned original train export | 982 | 969 | 13 | 13/13 |
| CORD-v2, first train shard only | 200 | 176 | 24 | 24/24 |
| SROIE curated, pinned train export | 626 | 625 | 1 | 1/1 |
| Total audited records, separate datasets | 1,808 | 1,770 | 38 | 38/38 |

The total is inventory accounting, not a combined benchmark or accuracy denominator.
Mapped means the supported native labels were converted; it does not mean full
13-header/line-item coverage, independent QA, aligned OCR gold or final eligibility.
Unsupported fields stay UNKNOWN and are masked. Public data is auxiliary only.

- Vietnamese Bill: decimal or ambiguous VND grouping, e.g. `47.759,93`,
  `17,120.0`, `85000.`. No automatic rounding or locale guessing.
- CORD: unhandled money prefixes/grouping (`Rp`, `@`, separators) or quantity
  syntax (`*4 Pcs`, `1,000`, `0,292X`). These need source/semantic review; rejection
  under mapping 0.2 does not imply the native dataset is erroneous.
- SROIE curated: `-1.73` is outside the current nonnegative money contract.
  Do not turn it positive or replace it with zero. Lead/TV1 must decide task scope.

Licenses and provenance strings are inherited publisher/curator declarations
from the existing preparation reports, not new independent license verification.
SROIE is the curated version, not the organizer archive. Keep versions separate.

## Actual retained files

Local directories (ignored by Git):

```text
data/processed/quarantine/vietnamese-bill-0.2/
data/processed/quarantine/cord-0.2/
data/processed/quarantine/sroie-curated-0.2/
output/datasets/public-quarantine-0.2.zip
```

Each `line-NNNNNN/` contains the unchanged native annotation record, the source
image, and rejection metadata. There were zero image-retention failures in this
run. The archive has 38 images, 38 native records, per-record rejections and three
family manifests/reports. It is a local handoff artifact, **not hosted by this Git
directory**. Its SHA256/availability are in
[artifact-index.json](../../handoffs/lead-feedback/artifact-index.json).

## Reproduce from the same pinned exports

From the repository root, use a new output directory for each command:

```powershell
python -m scripts.data.quarantine_public --input data/raw/vietnamese-bill-full-audit/export.jsonl --source-root data/raw/vietnamese-bill-full-audit --report data/registry/audits/vietnamese_bill_full_preparation.json --output NEW_VIETNAMESE_QUARANTINE
python -m scripts.data.quarantine_public --input data/raw/cord-first-train-shard/export.jsonl --source-root data/raw/cord-first-train-shard --report data/registry/audits/cord_full_preparation.json --output NEW_CORD_QUARANTINE
python -m scripts.data.quarantine_public --input data/raw/sroie-jsdnrs-audit/export.jsonl --source-root data/raw/sroie-jsdnrs-audit --report data/registry/audits/sroie_curated_full_preparation.json --output NEW_SROIE_QUARANTINE
```

The tool refuses export/report hash mismatch, duplicate rejection lines,
unaccounted cohort and overwriting. Missing images remain reported failures;
their native records are still retained. Mapping improvements require a new
version and source QA; do not overwrite these audit records or reclassify them
as verified canonical gold automatically.
