# Synthetic Table development sources

Four project-authored PNG scenes cover full borders, no borders, horizontal-only
and vertical-only lines. They share one base document and template, and all remain
in development. There is no private invoice data or external model.

Run `python scripts/generate_table_structure_sources.py` with Pillow 11.3.0 to
reproduce the PNG, evidence and expected JSON files. `provenance.json` records
generator and content hashes, coordinate system, version and QA state.

Evidence is authored from the literal source scene, not obtained by running OCR
on these PNGs. Expected values and block links are independently specified source
literals, not copied from a strategy output. They are software expectations and
have not received independent human gold QA. The structure strategy ignores
ruling pixels; the separate Reader test runs generated text PDFs through PDFium.

See [the evaluation report](../../../docs/table-structure-evaluation.md) for
commands, denominators, failures and the distinction from a scored benchmark.
