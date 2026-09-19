# Migration Status: runtime v1 → target v2

## Why this file exists

The repository already contains a functioning/partially implemented Week-1/2/3 stack built around five receipt fields:

- merchant_name
- receipt_date
- total_amount
- invoice_id
- merchant_address

The project plan was reset on 19/09/2026. The new product target is a Vietnamese invoice workflow with richer header fields, tax structure and line items.

## Source of truth

Current project/product requirements:
- README.md
- docs/project-plan.md
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
1. dataset/synthetic registry and v2 fixtures;
2. OCR/PDF evidence adapter remains reusable;
3. KIE moves to v2 header + tax + line items;
4. backend persistence/API moves to v2;
5. frontend review UI moves to v2;
6. export and final evaluation move to v2;
7. legacy v1 contracts/tests are removed only after v2 integration tests pass.

## Historical work

Closed Week-2/3 issues and PRs are retained only as Git history. They are not active requirements and should not be reopened to continue the old scope.
