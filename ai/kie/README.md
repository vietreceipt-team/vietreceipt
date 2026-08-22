# KIE VietReceipt

`ai/kie` implements the deterministic Week-2 baseline from GitHub Issue #16.
It consumes a canonical immutable `OCRResult` and produces a schema-valid
`KIEResult` for exactly five fields:

- `merchant_name`
- `receipt_date`
- `total_amount`
- `invoice_id`
- `merchant_address`

The implementation does not use an LLM/VLM, does not modify OCR output and
does not create Backend correction/effective-value state.

## Pipeline

```text
OCRResult validation
→ field-specific candidate generation
→ deterministic ranking
→ field-specific normalization
→ heuristic field confidence
→ versioned review policy
→ KIEResult validation
```

Main modules:

- `candidates/`: one generator per canonical field, with actual source block
  evidence, matched keywords/patterns, ambiguity and normalization indicators;
- `ranking/`: feature scoring, typed candidate-role priority and stable ranking;
- `normalization/`: safe deterministic normalization that never rewrites
  `predicted_value`;
- `confidence.py`: explainable heuristic field score;
- `review.py`: canonical review reasons and value-status decisions;
- `pipeline.py`: integration-ready `run_kie(...)`;
- `artifacts.py`: immutable per-run JSON persistence;
- `evaluation/`: field metrics, Real-vs-Oracle comparison and root-cause error
  analysis.

The root shared schemas remain the only public contract sources of truth:

- `schemas/ocr-result.schema.json`
- `schemas/kie-result.schema.json`
- `schemas/annotation-record.schema.json`

## Candidate ranking and confidence

Ranking weights and feature values live in
`resources/baseline-config-v0.1.yaml` under version
`baseline-ranking-v0.1`. Candidate ranking combines pattern, context, relative
layout and OCR evidence quality. Stable generation order breaks exact ties.
Primary invoice/receipt identifiers rank ahead of typed transaction/reference
fallback identifiers.

Public field confidence uses `heuristic-confidence-v0.2`. It combines:

- the best candidate ranking score;
- separation from the next same-role candidate;
- deterministic normalization success;
- ambiguity indicators.

The ranking score already contains pattern/context/layout/OCR evidence. Field
confidence is deterministic and clipped to `[0, 1]`, but it is **not a
calibrated probability of correctness**. It must not be used to auto-verify or
bypass human review. Thresholds in `heuristic-review-v0.2` are provisional and
must not be tuned on the held-out split.

## Evidence and immutable runs

Every populated field preserves real `source_block_ids` from the same OCR run.
Public `raw_text` is rebuilt from those blocks in `reading_order`; candidate
text is never accepted as fabricated public evidence.

Callers supply a UUID to `run_kie(...)`. Reprocessing requires a new
`kie_run_id`. `run_and_write_kie(...)` stores artifacts at:

```text
results/kie_outputs/<receipt_id>/<kie_run_id>.json
```

The writer opens the destination exclusively, so reusing an existing ID raises
`FileExistsError` and cannot overwrite the old run.

## Evaluation

The frozen split is:

```text
resources/kie-evaluation-split-v0.1.csv
```

It contains 20 development and 20 held-out receipt IDs. The evaluator reports
per-field, micro and macro Exact Match, status accuracy, normalization
accuracy, precision, recall, F1, coverage, review rate, error count and sample
count. Real OCR and
Oracle OCR are run separately; the report includes their metric gap and paired
root-cause analysis for:

- OCR omission;
- OCR substitution;
- candidate generation failure;
- candidate ranking failure;
- normalization failure;
- ambiguity;
- human-QA-confirmed annotation issue.

Run:

```bash
python scripts/evaluate_kie.py
```

Exit code `0` means verified evaluation completed. Exit code `2` means the
report was written with status
`WAITING_FOR_VERIFIED_FIELD_ANNOTATIONS`; all metrics remain `null`.

## Current data dependency

`data/kie_evaluation/manifest.json` intentionally contains no records while
the frozen 40-receipt set is waiting for independent five-field double
annotation, adjudication and verified Oracle OCR provenance. Do not convert
OCR transcription files into semantic KIE labels, mark pending data as
verified, or fabricate metrics.

The human workflow is frozen in `docs/gold-protocol.md`. A receipt becomes
evaluation-ready only after both annotations, all adjudication decisions and
the Oracle OCR artifact have been reviewed and their provenance recorded.

## Verification commands

```bash
python -m pytest
python tests/contracts/run_contract_tests.py
python scripts/evaluate_kie.py
git diff --check
```

The first two commands must pass. Until verified annotations exist, the third
command is expected to return exit code `2` with explicit waiting reasons, not
made-up evaluation numbers.
