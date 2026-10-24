> Follow-up 2026-10-24: use the [TV4 evaluator intake overlay and review workflow](tv4-review-followup.md). TV4 PR #69 now publishes the contract. The original v1 package remains unchanged.

# TV2 development / validation package for TV4

## Reproduce on the current dataset

Install requirements-data.txt plus the pinned TV3 OCR runtime. Use a Unicode font
matching generation.json. On Windows, set PADDLE_PDX_CACHE_HOME to an ASCII path.

```sh
python -m scripts.data.build_tv4_handoff --root data/synthetic/v0.2.0 --output results/tv2-local/tv4-dev-new --timeout 180
python -m scripts.data.finalize_tv4_handoff --root results/tv2-local/tv4-dev-new
python -m scripts.data.verify_tv4_handoff --root results/tv2-local/tv4-dev-new
```

Selection is frozen before inference: all 20 train/validation base documents,
three clean routes (text PDF, PNG, scanned PDF) plus blur PNG = 80 input files.
The six-family cycle's test-only layouts are excluded. No success-based filtering
or final mock/unseen-test source is included. Each input is attempted once in an
isolated reader subprocess; timeout/native failure is retained, not removed.
source-level base/template counts differ from derivative input-file counts.

## Contents

- selection.csv + selection-freeze.json: intended cohort and immutable selection hash.
- train-manifest.json / validation-manifest.json: every record, count, provenance,
  source/gold/evidence hashes and proposed experiment names.
- Each records/ directory: original source bytes, unchanged source gold,
  source cell/row regions, actual document-2.0 evidence with 1.3 page payload,
  route/config/runtime metadata, raw log, aligned-gold-candidate and alignment report.
- index.html and per-record review.html: full review gallery, including failures.
- failures.csv: reader failures and missing/ambiguous/unmatched/shared blocks.
- review-source-gold.json / review-template.json: pending reviewer input.
- summary.json + integrity-report.json: true counts and limited automated checks.

Identity: base_document_id / original_sample_id / source_sample_id identify the
source invoice. Each file has a unique record_id / sample_id and receipt UUID.
The source-gold file keeps original IDs. The derived review/aligned copies use
explicit per-input identity aliases; source values/statuses/rows stay unchanged.
Block IDs remain those actually returned by that input's reader run.

Source polygons come from the render specification and matching font metrics,
not detected/predicted rows. They are approximate source regions requiring spatial
QA, not independently reviewed spatial ground truth. Spatial source/evidence overlap proposes actual block IDs even when OCR glyphs
differ. Text agreement is a separate review signal. Missing actual blocks stay
unresolved. Source values/statuses never change to match predictions.

## Review and evaluator state

Membership/hash freeze is a development freeze only. qa_status stays PENDING_REVIEW.
All experiment fields are a proposal; the exact TV4 A/B protocol/schema is awaited.
These manifests are NOT described as passing an unpublished evaluator contract.
The current repository evaluator has no --output and no grouping-test module as
shown in the request. Contract-compatibility evidence is recorded separately.

After actual review, use the existing command (new reviewed output file):

```sh
python -m scripts.data.link_evidence --gold RECORD/review-source-gold.json --evidence RECORD/evidence.json --review RECORD/reviewed-mapping.json --output RECORD/reviewed-gold.json
```

Do not change SOURCE gold, approval metadata, sample membership or experiment
declaration merely to pass a gate. Explicitly report aligned-eligible vs source
denominators, and keep missing OCR regions for source-level evaluation.

## Oracle

No oracle evidence is supplied. selected_value_text records exactly the values
written to source by the renderer and is available for QA. A selected-value-text-v1
normalization oracle needs agreed rules and actual review, preserving all original
geometry, receipt/run/block IDs. It must not be inferred from KIE predictions.

## Coordination

See coordination-required.md for owners, precise missing inputs and acceptance.

## Shared contract check on Windows

Use `python -X utf8 tests/contracts/run_contract_tests.py` (or set PYTHONUTF8=1). The unflagged command can fail on Windows cp1252 decoding unrelated Vietnamese example text. The pinned requirements-contracts.txt versions were present and the UTF-8 run passed.
