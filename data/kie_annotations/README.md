# W3 five-field annotation workspace

`annotator_a/` and `annotator_b/` contain intentionally incomplete forms for
`R001`-`R040`. Null status and blank provenance/identity fields are not labels;
the forms must fail the canonical annotation schema until a named human fills
them from the authorized receipt image.

The two directories are independent work queues. Annotator B must not inspect
annotator A's files before submitting B. After both forms pass, run
`python scripts/w3_gold_workflow.py compare Rxxx` to create a `final/` draft
and, when A/B disagree, an `adjudication/` draft. Never overwrite the original
A/B records.

See `data/kie_evaluation/W3_INPUT_GUIDE.vi.md` for the complete procedure.
