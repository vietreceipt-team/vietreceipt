#!/usr/bin/env python3
"""Fail-closed checks for a VietReceipt V2 synthetic CSV manifest.

This checks data/annotation consistency, not extraction accuracy or OCR quality.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

FIELDS = frozenset(('invoice_template_number','invoice_symbol','invoice_number',
  'invoice_date','seller_name','seller_tax_id','seller_address','buyer_name',
  'buyer_tax_id','subtotal','tax_amount','total_amount','currency'))
LINE_FIELDS = ('description','unit','quantity','unit_price','amount')
SPLITS = frozenset(('train','validation','test','benchmark'))


def audit(manifest, root):
    problems, warnings = [], []
    seen, layout_splits, entries = set(), defaultdict(set), {}
    with Path(manifest).open(encoding='utf-8-sig', newline='') as handle:
        records = list(csv.DictReader(handle))
    if not records:
        return {'status':'FAILED','sample_count':0,'errors':['Empty manifest'],'warnings':[]}
    required = {'sample_id','split','layout_id','document_path','ground_truth_path'}
    if not required.issubset(records[0]):
        return {'status':'FAILED','sample_count':len(records),'errors':['Missing manifest columns: '+str(sorted(required-set(records[0])))],'warnings':[]}
    root = Path(root).resolve()
    def path_for(name, sample):
        p = (root/name).resolve()
        if not p.is_relative_to(root):
            raise ValueError(f'{sample}: file path escapes repository root')
        return p
    for n, row in enumerate(records, 2):
        sample = row['sample_id'].strip()
        split = row['split'].strip()
        layout = row['layout_id'].strip()
        if not sample or sample in seen:
            problems.append(f'row {n}: empty or repeated sample_id {sample!r}')
        seen.add(sample)
        if split not in SPLITS or not layout:
            problems.append(f'{sample}: invalid split/layout')
        layout_splits[layout].add(split)
        entries[sample] = row
        try:
            document = path_for(row['document_path'], sample)
            gold_file = path_for(row['ground_truth_path'], sample)
            if not document.is_file() or not gold_file.is_file():
                problems.append(f'{sample}: missing document/ground truth file')
                continue
            if document.suffix.lower() not in {'.pdf','.jpg','.jpeg','.png'}:
                warnings.append(f'{sample}: {document.suffix} is not an upload-supported input; render to PDF/PNG first')
            gold = json.loads(gold_file.read_text(encoding='utf-8'))
            if (gold.get('sample_id') != sample or gold.get('split') != split
                    or gold.get('template_id') != layout):
                problems.append(f'{sample}: label/manifest identity mismatch')
            fields = gold.get('fields', {})
            if set(fields) != FIELDS:
                problems.append(f'{sample}: header fields missing/extra: {sorted(FIELDS-set(fields))} / {sorted(set(fields)-FIELDS)}')
            for key, cell in fields.items():
                if not isinstance(cell, dict):
                    problems.append(f'{sample}: invalid cell {key}')
                    continue
                status, value = cell.get('annotation_status'), cell.get('normalized_value')
                if status == 'PRESENT' and value is None:
                    problems.append(f'{sample}: PRESENT has no normalized value: {key}')
                if status != 'PRESENT' and value is not None:
                    problems.append(f'{sample}: non-PRESENT has value: {key}')
            try:
                values = [fields[k]['normalized_value'] for k in ('subtotal','tax_amount','total_amount')]
                if all(type(v) is int and v >= 0 for v in values):
                    if values[0] + values[1] != values[2]:
                        problems.append(f'{sample}: subtotal + tax != total')
            except (KeyError, TypeError):
                pass
            for item in gold.get('line_items', []):
                if not all(isinstance(item.get(k), dict) for k in LINE_FIELDS):
                    problems.append(f'{sample}: line item has missing cells')
            if any(c.get('annotation_status') == 'PRESENT' and not c.get('source_block_ids')
                   for c in fields.values() if isinstance(c, dict)):
                warnings.append(f'{sample}: labels lack source_block_ids; not eligible for current evidence-linked KIE evaluator')
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(f'{sample}: {type(exc).__name__}: {exc}')
    for layout, groups in layout_splits.items():
        if len(groups) > 1:
            problems.append(f'layout family {layout!r} occurs in multiple splits: {sorted(groups)}')
    for sample, row in entries.items():
        parent = row.get('parent_sample_id', '').strip()
        if parent and parent in entries and entries[parent]['split'] != row['split']:
            problems.append(f'{sample}: parent {parent} crosses splits')
    return {'status':'FAILED' if problems else 'PASSED','sample_count':len(records),
            'layout_families':len(layout_splits),'errors':problems,'warnings':warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = audit(args.manifest, args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASSED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
