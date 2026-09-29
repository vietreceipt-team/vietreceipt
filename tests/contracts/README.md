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

## Invoice V2 additions

`python tests/contracts/run_contract_tests.py` also checks the canonical Invoice
V2 schema, required predicted/provenance/review/row metadata, non-PRESENT null
invariants and source linkage. It validates and reproduces the explicitly
synthetic `examples/invoice-v2-synthetic-*.json` pair. These are software contract
tests, not frozen-data accuracy results. Existing V1 checks remain in the runner.
