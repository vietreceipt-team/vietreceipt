# Contract tests

Run from the repository root:

```bash
python3 tests/contracts/run_contract_tests.py
```

The runner uses AJV Draft 2020-12 through `npx` to check valid examples and generated invalid cases. It also calls the shared linkage logic to prove that annotation receipt/run/block references match `examples/ocr-result.json`.

Covered negative cases include all annotation status invariants, canonical amount/date/ID types, real-record timestamps, OCR evidence consistency, cross-record linkage and the two KIE runtime invariants for source blocks and review reasons.
