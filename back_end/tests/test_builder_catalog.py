"""Offline regression check: python -m unittest discover -s tests."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch


config = ModuleType('modules.config')
config.GRAPHDB_READ = config.GRAPHDB_WRITE = 'http://unused.invalid'
spec = importlib.util.spec_from_file_location(
    'builder_under_test', Path(__file__).resolve().parents[1] / 'modules/db/swrl.py')
builder = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'modules.config': config}):
    spec.loader.exec_module(builder)


class BuilderCatalogTest(unittest.TestCase):
    def test_categories_labels_and_save_validation(self):
        rows = []
        def add(kind, name, label=None):
            row = {'kind': {'value': kind}, 'item': {'value': builder.EX + name}}
            if label:
                row['label'] = {'value': label}
            rows.append(row)

        for name in (*builder.OTHER_COMPLICATIONS, 'NoGeneralComplication'):
            for kind in ('special', 'complication'):
                add(kind, name)
        add('comorbidity', 'NoComorbidity')
        add('comorbidity', 'CustomFinding', 'โรคร่วมที่เพิ่มเอง')
        for name in ('DKA', 'hyperglycemia', 'Hypoglycemia', 'Microalbuminuria'):
            add('complication', name)
        add('comorbidity', 'ExistingLabel', 'ชื่อภาษาไทย (Existing label)')
        add('warning', 'Warning1', 'คำเตือนทดสอบ')
        client = MagicMock()
        client.query.return_value.convert.return_value = {'results': {'bindings': rows}}
        with patch.object(builder, 'SPARQLWrapper', return_value=client):
            catalog = builder.get_builder_catalog()

        fields = catalog['fields']
        self.assertEqual([fields[k]['label'] for k in ('comorbidity', 'complication', 'special')],
                         ['โรคร่วม', 'ภาวะแทรกซ้อนทั่วไป', 'ภาวะแทรกซ้อนอื่นๆ'])
        self.assertEqual({i['value'] for i in fields['special']['options']},
                         {builder.EX + name for name in builder.OTHER_COMPLICATIONS})
        self.assertEqual({i['value'] for i in fields['complication']['options']},
                         {builder.EX + name for name in ('NoGeneralComplication', 'DKA',
                          'hyperglycemia', 'Hypoglycemia', 'Microalbuminuria')})
        labels = [i['label'] for i in fields['comorbidity']['options']]
        self.assertIn('ไม่มีโรคร่วม (No Comorbidity)', labels)
        self.assertIn('โรคร่วมที่เพิ่มเอง (Custom Finding)', labels)
        self.assertIn('ชื่อภาษาไทย (Existing label)', labels)
        general = {i['value']: i['label'] for i in fields['complication']['options']}
        self.assertEqual(general[builder.EX + 'DKA'], 'ภาวะกรดคีโตนในเลือดสูง (DKA)')
        for identifier, english in (('hyperglycemia', 'Hyperglycemia'),
                                    ('Hypoglycemia', 'Hypoglycemia'),
                                    ('Microalbuminuria', 'Microalbuminuria')):
            self.assertIn('ภาวะ', general[builder.EX + identifier])
            self.assertTrue(general[builder.EX + identifier].endswith(f'({english})'))

        data = {'name': 'ทดสอบ', 'conditions': [
            {'field': 'special', 'op': 'eq', 'value': builder.EX + 'HeartDisease'}],
            'outputs': [{'action': 'warning', 'result': builder.EX + 'Warning1'}]}
        rule = builder.compile_builder_rule(data, catalog)['swrl_expression']
        self.assertIn('ex:hasSpecialComplication(?pe, ex:HeartDisease)', rule)
        data['conditions'][0]['field'] = 'complication'
        with self.assertRaises(ValueError):
            builder.compile_builder_rule(data, catalog)


if __name__ == '__main__':
    unittest.main()
