# Dataset Strategy v2

## Decision

Manual collection of hundreds of real invoices is **not a core project requirement**. VietReceipt uses public datasets and team-generated synthetic Vietnamese invoices for development and formal prototype evaluation.

A real-invoice pilot may be added later only when data-use permission is clear. It is optional and must be reported separately.

## Dataset families

### Vietnamese Bill Extraction

Use for Vietnamese-language extraction experiments and mapping to VietReceipt fields where the source annotations support them. Do not assume every canonical field exists in this dataset.

### CORD

Use for receipt layout and line-item experiments and as an external public benchmark. It is not Vietnamese-enterprise evidence.

### SROIE

Use as a public scanned-receipt OCR/KIE benchmark. Keep its native task/labels distinct from the VietReceipt canonical schema.

### VietReceipt Synthetic

Generate Vietnamese invoice-like documents from controlled templates. Ground truth is generated together with the document.

Recommended synthetic variability:

- seller/buyer identity;
- tax IDs;
- invoice number/date;
- totals and VAT;
- multiple tax-rate patterns;
- 1..N line items;
- font/spacing/layout variation;
- image rotation/perspective;
- blur/noise/contrast;
- scan-like and photograph-like rendering;
- PDF text and PDF scan variants.

Synthetic documents are not counted as real invoices.

## Provenance

Every sample used in an experiment must retain:

- dataset family;
- dataset version/snapshot;
- original sample ID;
- template/layout ID when known;
- source type;
- synthetic/real/public flag;
- augmentation parent ID when applicable;
- split;
- mapping/annotation version.

## Split policy

1. Prefer official public train/dev/test splits when they exist and fit the experiment.
2. If VietReceipt creates its own split, variants derived from the same base document stay in the same split.
3. For synthetic data, split by base template/document identity before generating augmented variants.
4. Freeze the final test manifest before final tuning.
5. A public final test sample must never be used to choose rules, prompts, thresholds or preprocessing.
6. Report external-dataset results separately; do not pool unrelated datasets into one headline accuracy.

## Ground truth

Public labels are mapped only when their meaning matches the canonical VietReceipt field. Unsupported fields remain unavailable rather than fabricated.

Synthetic ground truth is produced from the generator source values. A validation script must check arithmetic consistency and schema validity.

## Claims

Allowed:
- performance on a named public dataset/split;
- performance on VietReceipt Synthetic;
- comparison across input degradation slices;
- prototype web workflow demonstration.

Not allowed without additional evidence:
- “works on all Vietnamese invoices”;
- “saves accountants X% time”;
- “enterprise-ready accuracy”;
- treating synthetic/public foreign receipts as representative Vietnamese-company invoices.

## TV2 ownership

TV2 maintains:

- dataset registry;
- licenses/access notes;
- download/preparation instructions;
- mapping scripts;
- synthetic generator versions;
- split manifests;
- ground-truth validation;
- final benchmark manifest.
