# Migration Status: runtime v1 → target v2

## Why this file exists

The repository already contains a functioning/partially implemented Week-1/2/3 stack built around five receipt fields:

- merchant_name
- receipt_date
- total_amount
- invoice_id
- merchant_address

The project target is now a Vietnamese invoice workflow with richer header fields, tax structure, grouped line items, source-aware PDF/OCR routing and thesis-grade evaluation.

## Source of truth

Current project/product/research requirements:
- README.md
- docs/project-plan.md
- docs/research-design.md
- docs/dataset-strategy.md
- docs/integration-contracts.md
- docs/evaluation-plan.md

Target machine contracts:
- schemas/invoice-kie-result.v2.schema.json
- schemas/invoice-annotation.v2.schema.json
- openapi/openapi-v2.yaml

Legacy runtime contracts kept temporarily so existing code does not break during migration:
- schemas/kie-result.schema.json
- schemas/annotation-record.schema.json
- openapi/openapi.yaml
- existing five-field backend/frontend/KIE implementation

## Migration rule

No new feature work should extend the five-field contract.

Migration should happen module-by-module:

1. dataset registry, synthetic generator and template-disjoint split manifests;
2. independent mock final-test registry;
3. OCR/PDF evidence adapter remains reusable;
4. source router adds direct-text PDF path and OCR fallback;
5. KIE moves to v2 header + tax + **row-grouped line items**;
6. backend persistence/API moves to v2;
7. frontend review UI moves to v2, including line-item editing/evidence;
8. export moves to v2 header + linked line-item tables;
9. v2 end-to-end evaluation runner, baseline/ablation runner and robustness slices are added;
10. legacy v1 contracts/tests are removed only after v2 integration tests pass.

## Research-critical migration gates

The following are required before the project can support the intended thesis claims.

### Gate A — source routing
- born-digital PDF direct extraction exists;
- scanned PDF/image OCR path exists;
- both converge to one evidence contract;
- OCR-all baseline can still be run for E1 comparison.

### Gate B — structured line items
- v2 runtime produces grouped line records;
- rows preserve evidence;
- partial/unreadable rows are not silently dropped;
- row and cell metrics can be computed.

### Gate C — frozen evaluation
- template-disjoint unseen test manifest exists;
- independent mock-test manifest exists;
- final evaluation code names dataset/version/split/commit;
- end-to-end metrics are generated from untouched frozen sets.

### Gate D — reproducible comparison
- baseline/ablation configs are versioned;
- the same eligible sample set is used for controlled comparisons;
- raw machine output is preserved for error analysis.

## Historical work

Closed Week-2/3 issues and PRs are retained only as Git history. They are not active requirements and should not be reopened to continue the old scope.

Existing v1 metrics are useful only as historical/baseline evidence; they are not final evidence for the v2 invoice thesis.
