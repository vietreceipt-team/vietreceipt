"""Safety checks for synthetic manifest validation."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.validate_invoice_dataset_v2 import FIELDS, audit


class DatasetAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'documents').mkdir()
        (self.root / 'labels').mkdir()
        self.rows = []

    def add(self, sample='A', layout='a', split='train', parent=''):
        (self.root / f'documents/{sample}.pdf').write_bytes(b'dummy')
        fields = {k: {'annotation_status':'UNKNOWN','normalized_value':None,'source_block_ids':[]} for k in FIELDS}
        gold = {'sample_id':sample,'template_id':layout,'split':split,'fields':fields,'line_items':[]}
        (self.root / f'labels/{sample}.json').write_text(json.dumps(gold))
        self.rows.append(dict(sample_id=sample,layout_id=layout,split=split,
            document_path=f'documents/{sample}.pdf',ground_truth_path=f'labels/{sample}.json',
            parent_sample_id=parent))

    def check(self):
        manifest = self.root / 'manifest.csv'
        with manifest.open('w',newline='') as f:
            writer = csv.DictWriter(f,fieldnames=list(self.rows[0]))
            writer.writeheader()
            writer.writerows(self.rows)
        return audit(manifest,self.root)

    def test_valid_manifest(self):
        self.add()
        self.assertEqual(self.check()['status'],'PASSED')

    def test_layout_crosses_splits(self):
        self.add('A','a','train')
        self.add('B','a','test')
        self.assertEqual(self.check()['status'],'FAILED')

    def test_missing_header_field(self):
        self.add()
        path = self.root / 'labels/A.json'
        data = json.loads(path.read_text())
        del data['fields']['currency']
        path.write_text(json.dumps(data))
        self.assertIn('header fields missing',str(self.check()['errors']))

    def test_parent_leakage(self):
        self.add('A','a','train')
        self.add('B','b','test','A')
        self.assertIn('crosses splits',str(self.check()['errors']))


if __name__ == '__main__':
    unittest.main()
