# Annotation / Ground-truth Contract v2

## Scope
Ground truth in VietReceipt comes from:
1. public dataset annotations mapped to the VietReceipt schema when semantically compatible;
2. automatically generated truth from VietReceipt Synthetic.

Manual collection/annotation of hundreds of business invoices is not required by the current plan.

## Canonical fields
Header labels follow `docs/integration-contracts.md`. Line-item labels are structured rows rather than one free-text field.

## Mapping rules
- Map only labels whose meaning matches the VietReceipt field.
- Preserve original dataset sample IDs and source label names.
- Leave unsupported canonical fields unavailable; never infer them from outside knowledge.
- Store mapping version and dataset snapshot.
- Synthetic samples keep generator template/version and source values.

## Status
Ground-truth values may use PRESENT, NOT_PRESENT, UNREADABLE, AMBIGUOUS or UNKNOWN where the source supports that distinction.

## Evidence
When bounding boxes/blocks exist, mapped annotations should retain evidence references. If the source dataset lacks geometry, record that limitation rather than fabricating coordinates.

## QA
Synthetic ground truth must pass schema and arithmetic checks. Public mapping scripts must have small manually inspected fixtures before bulk conversion.

Final test manifests are immutable after freeze.
