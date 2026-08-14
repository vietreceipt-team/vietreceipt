# Contract tests

## Prerequisite

- Python 3.10 or newer.
- Pinned dependency from the repository root:

```bash
python3 -m pip install -r requirements-contracts.txt
```

The suite uses pinned Python dependencies for JSON Schema Draft 2020-12, YAML parsing and OpenAPI 3.1 validation. It does not require Node.js, npm, `npx` or AJV.

## Run

From the repository root:

```bash
python3 tests/contracts/run_contract_tests.py
```

The runner validates all three schemas/examples, parses and validates OpenAPI 3.1, and generates positive and negative annotation/KIE cases. It also prevents drift among OpenAPI, the receipt state machine and KIE review reasons; checks correction/verification concurrency shapes; and proves OCR run-level block/reading-order plus annotation linkage invariants.

GitHub Actions runs the same command on every relevant push and Pull Request.
