import ast
import json
import re
import unittest
from pathlib import Path
from rdflib import Graph

class RuleNameTest(unittest.TestCase):
    def test_delete_message_names_and_fallback(self):
        source = Path(__file__).resolve().parents[1] / 'modules/db/admin_repository.py'
        names = {'_delete_catalog_item', 'delete_category_from_ontology'}
        nodes = [n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name in names]
        for category in (False, True):
            for label in ('คำแนะนำสำหรับผู้ป่วย', '', None):
                with self.subTest(category=category, label=label):
                    target = 'rdfs:subClassOf ex:Exercise' if category else 'a ex:Frequency'
                    label_triple = '' if label is None else 'ex:Internal123 rdfs:label ' + json.dumps(label, ensure_ascii=False) + ' .'
                    graph = Graph().parse(data='''
                        @prefix ex: <http://example.org/diabetes#> .
                        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                        @prefix swrl: <http://www.w3.org/2003/11/swrl#> .
                        ex:Item ''' + target + ''' .
                        ex:Internal123 a swrl:Imp ; swrl:head ([swrl:argument2 ex:Item]) .
                        ''' + label_triple, format='turtle')
                    before = set(graph)
                    class Client:
                        def __init__(self, endpoint): pass
                        def setReturnFormat(self, value): pass
                        def setQuery(self, query): self.query_text = query
                        def query(self):
                            self.result = json.loads(graph.query(self.query_text).serialize(format='json'))
                            return self
                        def convert(self): return self.result
                        def setMethod(self, method): raise AssertionError('Must not delete')
                    ns = dict(re=re, SPARQLWrapper=Client, GRAPHDB_READ='read', GRAPHDB_WRITE='write', JSON='json')
                    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), ns)
                    result = ns['delete_category_from_ontology']('Item') if category else ns['_delete_catalog_item']('Item', 'Frequency', 'ความถี่')
                    self.assertFalse(result['success'])
                    self.assertIn(label or 'Internal123', result['message'])
                    if label: self.assertNotIn('Internal123', result['message'])
                    self.assertEqual(before, set(graph))

if __name__ == '__main__': unittest.main()
