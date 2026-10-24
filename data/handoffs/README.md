# TV4 development / validation handoff

tv4-dev-v1.zip is a self-contained, fictional synthetic development artifact.
It contains all 80 predeclared inputs from 20 source invoices: 60 train files,
20 validation files, three clean routes and blur PNG. No final test is included.

Extract to a new directory and open index.html. Read summary.json,
integrity-report.json, failures.csv and the separate train/validation manifests.
Original source gold, actual reader evidence, source cell/row regions, candidate
aligned gold, complete logs/config and pending mapping-review templates are inside.

QA status is PENDING_REVIEW, not VERIFIED. All 80 records have proposed spatial
block links; OCR text disagreement is exposed rather than changed into source
absence. The archive is for review and contract integration, not final accuracy.
See docs/data/tv4-handoff.md and docs/data/coordination-required.md.

The SHA-256 sidecar and package JSON preserve the published artifact identity.
The package contains no public receipt images and no model weights.

## Lead feedback follow-up

The [artifact index](lead-feedback/artifact-index.json) lists exact archive hashes and availability. The [80-record review queue](lead-feedback/review-queue.csv) is unassigned and pending independent review. See [acceptance status](../../docs/data/lead-feedback-acceptance.md). No reviewed/final release is claimed. The public quarantine archive is local only; its metadata reports are tracked in data/registry/quarantine.
