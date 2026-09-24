# Dataset Strategy v3

## Decision

Manual collection of hundreds of real invoices is **not a core project requirement**. VietReceipt uses public datasets and team-generated synthetic Vietnamese invoices for development and formal prototype evaluation.

A real-invoice pilot may be added later only when data-use permission is clear. It is optional and must be reported separately.

The dataset design must support two different questions:

1. **in-distribution performance** on layouts similar to development data;
2. **generalization performance** on layouts/templates not used during development.

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

### VietReceipt Independent Mock Test

Create a smaller final-test family manually or with a separate process that **does not reuse the main synthetic generator templates**.

Examples:
- invoices authored independently in Word/Excel/HTML/design tools;
- different table grids and header positions;
- print → photograph / scan variants;
- unusual but still in-scope layouts.

This set is intended to challenge the generator-specific assumptions of the main synthetic family. It must remain untouched until the final evaluation phase.

## Provenance

Every sample used in an experiment must retain:

- dataset family;
- dataset version/snapshot;
- original sample ID;
- template/layout ID when known;
- source type;
- synthetic/real/public flag;
- augmentation parent ID when applicable;
- degradation label / severity when applicable;
- split;
- mapping/annotation version.

## Split policy

1. Prefer official public train/dev/test splits when they exist and fit the experiment.
2. If VietReceipt creates its own split, variants derived from the same base document stay in the same split.
3. **Synthetic generalization split is template-disjoint:** template IDs reserved for final unseen-template testing cannot appear in development/validation.
4. Split by base template/document identity **before** generating augmented variants.
5. Freeze the final test manifest before final tuning.
6. A final test sample must never be used to choose rules, prompts, thresholds, preprocessing or model configurations.
7. Report external-dataset results separately; do not pool unrelated datasets into one headline accuracy.
8. The independent mock test remains separate from synthetic generator evaluation.

### Recommended synthetic layout partition

The exact counts can change, but the principle should resemble:

- development templates: ~60%;
- validation templates: ~20%;
- final unseen templates: ~20%.

Do not use a random document-level split across the same template family as the only generalization test.

## Ground truth

Public labels are mapped only when their meaning matches the canonical VietReceipt field. Unsupported fields remain unavailable rather than fabricated.

Synthetic ground truth is produced from the generator source values. A validation script must check:

- JSON-schema validity;
- subtotal / tax / total arithmetic consistency;
- line-item arithmetic where the invoice format supports it;
- required provenance;
- absence of duplicate IDs;
- correct parent/variant linkage.

Independent mock data must be annotated separately from the main generator output so it does not inherit generator assumptions.

## Evaluation slices

When sample count permits, final reports should slice performance by:

- source route: text-PDF / scanned-PDF / image;
- template: seen / unseen;
- quality: clean / blur-noise / rotation-perspective / scan-like;
- line-item complexity: single-line / multi-line / many-item;
- dataset family.

A single pooled score must not replace these slices.

## Claims

Allowed:
- performance on a named public dataset/split;
- performance on VietReceipt Synthetic;
- performance on template-disjoint unseen layouts;
- performance on independent mock invoices;
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
- independent mock-test registry;
- split manifests;
- ground-truth validation;
- final benchmark manifest.
