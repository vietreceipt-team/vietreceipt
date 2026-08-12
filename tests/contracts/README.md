# Contract tests

## Prerequisite

- Python 3.10 or newer.
- Pinned dependency from the repository root:

```bash
python3 -m pip install -r requirements-contracts.txt
```

The suite uses Python `jsonschema` Draft 2020-12 with format checking. It does not require Node.js, npm, `npx` or AJV.

## Run

From the repository root:

```bash
python3 tests/contracts/run_contract_tests.py
```

The runner validates all three schemas/examples, generates positive and negative annotation/KIE cases, and invokes the shared linkage logic proving that annotation receipt/run/block references match `examples/ocr-result.json`.

GitHub Actions runs the same command on every relevant push and Pull Request.
