# Issue #49 verification record

Verified locally on 2026-09-30, Python 3.12.13, branch `feat/49-kie-v2`, base
`8426179dfc813d51026e5d301d6c0ad7967fa921`. Implementation is uncommitted at the
user's request. No branch was reset, no PR was merged, and nothing was pushed.
No applicable AGENTS.md was found in the worktree or its directory ancestors.

The isolated environment was `/tmp/vietreceipt-49-py312`. `env -u PYTHONPATH`
removes the workstation's unrelated ROS package paths. Installed dependencies:
`requirements-contracts.txt`, Ruff 0.16.9, Pillow 10.4.0, jiwer 3.0.3 and numpy
1.26.4. OCR regression tests use their existing fake engine; model weights and
private datasets were not downloaded.

## Results

| Check | Final result |
| --- | --- |
| V2 extraction + evaluator unit tests | 51 passed, 0 failed, 0 skipped |
| Legacy KIE baseline/evaluation/artifact tests | 41 passed, 0 failed, 0 skipped (included below) |
| Complete repository `tests/` discovery, including OCR regression | 116 passed, 0 failed, 0 skipped |
| Shared contract suite | PASS: V2 2 positive / 25 negative; V1 9 positive / 23 negative, plus OpenAPI and cross-record invariants |
| Exact PR #53 provider loader and validators | 2 synthetic inputs passed: single-page and document envelope |
| V2 and V1 missing-data evaluator CLI guards | 2 passed: expected exit 2 and null metrics |
| Ruff lint / format | PASS; 14 new Python files formatted |
| Compile/import checks | PASS |
| Dependency consistency | PASS: no broken requirements |
| `git diff --check` | PASS |

Counts above are software test cases, not dataset accuracy. The implementation
initially failed two synthetic regressions (short seller label shadowing tax ID,
equivalent currency aliases treated as competing candidates); both were fixed.
Additional review added guards for interleaved seller/buyer sections, mixed
currencies, transport-invalid source text and ambiguous description continuations.
Early expanded-suite import errors were missing Pillow/numpy in the isolated
environment; pinned dependencies were installed and the complete suite rerun.
No failed or skipped tests are concealed in the final counts.

## Commands

```bash
env -u PYTHONPATH /tmp/vietreceipt-49-py312/bin/python -m unittest tests.test_kie_v2 tests.test_kie_v2_evaluation -q
env -u PYTHONPATH /tmp/vietreceipt-49-py312/bin/python -m unittest discover -s tests -q
env -u PYTHONPATH /tmp/vietreceipt-49-py312/bin/python tests/contracts/run_contract_tests.py
env -u PYTHONPATH /tmp/vietreceipt-49-py312/bin/python -m pip check
/tmp/vietreceipt-49-py312/bin/ruff check ai/kie/v2 tests/kie_v2_fixtures.py tests/test_kie_v2.py tests/test_kie_v2_evaluation.py tests/contracts/invoice_v2.py scripts/evaluate_invoice_kie.py
/tmp/vietreceipt-49-py312/bin/ruff format --check ai/kie/v2 tests/kie_v2_fixtures.py tests/test_kie_v2.py tests/test_kie_v2_evaluation.py tests/contracts/invoice_v2.py scripts/evaluate_invoice_kie.py
env -u PYTHONPATH /tmp/vietreceipt-49-py312/bin/python -m compileall -q ai/kie scripts/evaluate_invoice_kie.py tests/test_kie_v2.py tests/test_kie_v2_evaluation.py tests/kie_v2_fixtures.py tests/contracts
git diff --check
```

The CLI guards were checked with the following Python subprocess assertions:

```python
import json
import subprocess
import sys
from pathlib import Path

checks = [
    ('scripts/evaluate_invoice_kie.py', [], 'WAITING_FOR_VERIFIED_V2_GOLD'),
    ('scripts/evaluate_kie.py', ['--report', '/tmp/vietreceipt-49-legacy-waiting.json'],
     'WAITING_FOR_VERIFIED_FIELD_ANNOTATIONS'),
]
for script, extra, status in checks:
    result = subprocess.run([sys.executable, script, *extra], capture_output=True, text=True)
    report = json.loads(result.stdout) if not extra else json.loads(Path(extra[1]).read_text())
    assert result.returncode == 2
    assert report['status'] == status and report['metrics'] is None
```

## Exact TV5 seam probe

PR refs were fetched read-only without merging. This probe was run with the Python
3.12 environment above and the inspected PR #53 head recorded in `kie-v2.md`:

```python
import os
import subprocess
import sys
import types
from pathlib import Path
from tests.kie_v2_fixtures import invoice, evidence, document, KIE_RUN, RECEIPT, OCR_RUN

root = Path.cwd()
package = types.ModuleType('tv5_probe')
package.__path__ = []
sys.modules['tv5_probe'] = package
for name in ('errors', 'contracts', 'providers'):
    code = subprocess.check_output(
        ['git', 'show', f'origin/pr-53:backend/app/v2/{name}.py'], text=True)
    module = types.ModuleType(f'tv5_probe.{name}')
    module.__file__ = str(root / 'backend/app/v2' / f'{name}.py')
    sys.modules[module.__name__] = module
    exec(compile(code, module.__file__, 'exec'), module.__dict__)
from tv5_probe import providers, contracts
os.environ['V2_KIE_CALLABLE'] = 'ai.kie.v2:extract_invoice'
fixtures = [
    invoice(tax_groups=True),
    document(invoice(), evidence([('Synthetic second page', .1, .1)], prefix='p1')),
]
for source in fixtures:
    contracts.validate_evidence(source, RECEIPT, OCR_RUN)
    output = providers.configured_kie(source, kie_run_id=str(KIE_RUN))
    contracts.validate_result(output, source, RECEIPT, str(KIE_RUN), OCR_RUN)
```

This proves callable/contract compatibility with the updated canonical schema.
It is not HTTP, worker, real OCR/PDF or browser E2E evidence. Full deployment
integration and frozen TV2 final evaluation remain external acceptance work.
