# Final-test and independent-mock policy

Development synthetic v0.2.0 is NOT a final test, including rows whose split is
test. All generated rows carry final_eligible=false. Do not use these rows for
untouched final claims after development inspection.

The main split is template-disjoint: three training families, one validation
family, two test families. Base documents are assigned before augmentation.
Variants inherit the parent's split and layout. These six layouts are a starter
collection, not proof of generalization; corporate/minimal variants still share
generator assumptions.

An independent author must create separate mock documents without reusing this
generator, record author/tool/source/version and original file hashes, and have
a different person review each annotation. Use clean/missing/ambiguous/long-table,
image, text-PDF, scanned-PDF and degraded samples. Do not generate this set with
the synthetic generator and rename it independent. The 100-150 target mentioned
in the PR discussion is a planning target, not an existing artifact.

Before final tuning: approve the experiment protocol/configuration commit,
verify labels, confirm no test was used for tuning, set final eligibility through
a documented version change, and freeze test-only inventory with:

```sh
python -m scripts.data.freeze_dataset --manifest FINAL_TEST_CSV --root DATASET_ROOT --review SIGNED_REVIEW_JSON --output final_test_inventory_v1.json
```

Review fields: manifest_sha256, reviewed_by, independent_review=true,
used_for_tuning=false, configuration_commit, dataset_version, timezone-aware
frozen_at, protocol. The command refuses development-only records, non-test rows,
failed QA, wrong hashes and overwrite. An inventory is not automatically a
KIE evaluator manifest. Evidence-linked gold needs its own reviewed mapping.

Keep frozen inventories immutable. If a final sample informs a model/rule change,
retire the old final claim and create a new independent version. Do not edit
gold merely to match predictions. Preserve raw predictions, failures, input hashes,
configuration, code commit, run date and dataset/split/version for every result.
