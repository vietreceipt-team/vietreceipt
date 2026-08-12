# Contract tests

Install the small validation-only dependency set and run:

```text
python -m pip install -r tests/contracts/requirements.txt
python -m unittest tests.contracts.test_contracts
```

The suite validates the committed OCR/KIE examples, KIE v1.1 negative semantic cases, canonical field typing/name matching, and receipt lifecycle response requirements. It does not run OCR or KIE models.
