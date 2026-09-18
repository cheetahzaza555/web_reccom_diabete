"""Exercise the actual catalog SPARQL and compiled R2 rules without a DB write."""
import io
import json
import unittest
from unittest.mock import patch

from flask import Flask
from rdflib import Graph, Namespace, RDF
from owlready2 import World, sync_reasoner_pellet

from modules.db.swrl import EX, get_builder_catalog, compile_builder_rule, _build_rule_insert_query


def fixture():
    return Graph().parse(data='''
        @prefix ex: <http://example.org/diabetes#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        ex:Patient a owl:Class . ex:DiabeteType a owl:Class .
        ex:Exercise a owl:Class . ex:Aerobic a owl:Class ; rdfs:subClassOf ex:Exercise .
        ex:KindOfExercise a owl:Class . ex:Complication a owl:Class .
        ex:Comorbidity a owl:Class . ex:Intensity a owl:Class .
        ex:Frequency a owl:Class . ex:WarningAvoidExercise a owl:Class .
        ex:PatientWarning a owl:Class .
        ex:diabetType a owl:ObjectProperty . ex:hasComorbidity a owl:ObjectProperty .
        ex:hasComplication a owl:ObjectProperty . ex:hasSpecialComplication a owl:ObjectProperty .
        ex:favoriteExercise a owl:ObjectProperty . ex:hasKindOfExercise a owl:ObjectProperty .
        ex:recommendedExercise a owl:ObjectProperty . ex:intensityOfExercise a owl:ObjectProperty .
        ex:exerciseFrequency a owl:ObjectProperty . ex:avoidExercise a owl:ObjectProperty .
        ex:hasPatientWarning a owl:ObjectProperty . ex:metValue a owl:DatatypeProperty ; rdfs:range xsd:decimal .
        ex:T2DM a ex:DiabeteType . ex:T1DM a ex:DiabeteType .
        ex:NoComorbidity a ex:Comorbidity .
        ex:NoGeneralComplication a ex:Complication . ex:NoOtherComplication a ex:Complication .
        ex:Moderate a ex:Intensity . ex:Light a ex:Intensity . ex:Vigorous a ex:Intensity .
        ex:Freq1 a ex:Frequency . ex:Freq2 a ex:Frequency . ex:Freq3 a ex:Frequency .
        ex:Avoid1 a ex:WarningAvoidExercise . ex:Avoid2 a ex:WarningAvoidExercise . ex:Avoid3 a ex:WarningAvoidExercise .
        ex:Warning1 a ex:PatientWarning .
        ex:WalkKind a ex:KindOfExercise . ex:OtherKind a ex:KindOfExercise .
        ex:17101 a ex:Exercise, ex:Aerobic ; ex:hasKindOfExercise ex:WalkKind ; ex:metValue 3.0 .
        ex:17102 a ex:Exercise, ex:Aerobic ; ex:hasKindOfExercise ex:WalkKind ; ex:metValue 6.0 .
        ex:17103 a ex:Exercise, ex:Aerobic ; ex:hasKindOfExercise ex:WalkKind ; ex:metValue 2.9 .
        ex:17104 a ex:Exercise, ex:Aerobic ; ex:hasKindOfExercise ex:WalkKind ; ex:metValue 6.1 .
        ex:17105 a ex:Exercise, ex:Aerobic ; ex:hasKindOfExercise ex:OtherKind ; ex:metValue 4.0 .
        ex:17106 a ex:Exercise ; ex:hasKindOfExercise ex:WalkKind ; ex:metValue 4.0 .
    ''', format='turtle')


def read_catalog(graph):
    with patch('modules.db.swrl.SPARQLWrapper') as wrapper:
        client = wrapper.return_value
        client.query.return_value.convert.side_effect = lambda: json.loads(graph.query(client.setQuery.call_args.args[0]).serialize(format='json'))
        return get_builder_catalog()


def r2(category='Exercise'):
    return {'name': 'R2 form test', 'conditions': [
        {'field': 'type', 'op': 'eq', 'value': EX + 'T2DM'},
        {'field': 'comorbidity', 'op': 'eq', 'value': EX + 'NoComorbidity'},
        {'field': 'complication', 'op': 'eq', 'value': EX + 'NoGeneralComplication'},
        {'field': 'complication', 'op': 'eq', 'value': EX + 'NoOtherComplication'},
    ], 'outputs': [
        {'action': 'exercise', 'result': EX + category, 'intensity': EX + 'Moderate', 'use_favorites': True},
        *[{'action': 'frequency', 'result': EX + f'Freq{i}'} for i in range(1, 4)],
        *[{'action': 'avoid', 'result': EX + f'Avoid{i}'} for i in range(1, 4)],
    ]}


class R2Tests(unittest.TestCase):
    def test_catalog_queries_actual_schema_and_rule_constants(self):
        graph = fixture()
        graph.parse(data='''
          @prefix ex: <http://example.org/diabetes#> .
          @prefix swrl: <http://www.w3.org/2003/11/swrl#> .
          [] swrl:propertyPredicate ex:diabetType ; swrl:argument2 ex:TypeFromRule .
          [] swrl:propertyPredicate ex:diabetType ; swrl:argument2 ex:variable .
          ex:variable a swrl:Variable .
        ''', format='turtle')
        cat = read_catalog(graph)
        types = {item['value'] for item in cat['fields']['type']['options']}
        self.assertTrue({EX + 'T2DM', EX + 'T1DM', EX + 'TypeFromRule'} <= types)
        self.assertNotIn(EX + 'variable', types)
        self.assertIn(EX + 'NoOtherComplication', {v['value'] for v in cat['fields']['complication']['options']})
        categories = {v['value'] for v in cat['results']['exercise']}
        self.assertIn(EX + 'Aerobic', categories)
        self.assertNotIn(EX + '17101', categories)
        self.assertEqual(len(cat['results']['frequency']), 3)

    def test_r2_reasoner_boundaries_and_all_outputs(self):
        for category, intensity, expected in [('Exercise', 'Moderate', {'17101', '17102', '17106'}), ('Aerobic', 'Moderate', {'17101', '17102'}), ('Exercise', 'Light', {'17103'}), ('Exercise', 'Vigorous', {'17104'})]:
            with self.subTest(category=category, intensity=intensity):
                graph = fixture()
                cat = read_catalog(graph)
                data = r2(category)
                data['outputs'][0]['intensity'] = EX + intensity
                query, _ = _build_rule_insert_query(**compile_builder_rule(data, cat))
                graph.update(query)
                ex = Namespace(EX)
                for patient, kind, complete, favorite in [('match', 'T2DM', True, True), ('wrongType', 'T1DM', True, True), ('missingFact', 'T2DM', False, True), ('noFavorite', 'T2DM', True, False)]:
                    graph.add((ex[patient], RDF.type, ex.Patient))
                    graph.add((ex[patient], ex.diabetType, ex[kind]))
                    graph.add((ex[patient], ex.hasComorbidity, ex.NoComorbidity))
                    graph.add((ex[patient], ex.hasComplication, ex.NoGeneralComplication))
                    if complete:
                        graph.add((ex[patient], ex.hasComplication, ex.NoOtherComplication))
                    if favorite:
                        graph.add((ex[patient], ex.favoriteExercise, ex.WalkKind))
                world = World()
                try:
                    world.get_ontology('http://example.org/test').load(fileobj=io.BytesIO(graph.serialize(format='nt', encoding='utf-8')), format='ntriples')
                    sync_reasoner_pellet(world, infer_property_values=True, infer_data_property_values=True, debug=0)
                    p = world[EX + 'match']
                    self.assertEqual({item.name for item in p.recommendedExercise}, expected)
                    self.assertEqual({item.name for item in p.intensityOfExercise}, {intensity})
                    self.assertEqual({item.name for item in p.exerciseFrequency}, {'Freq1', 'Freq2', 'Freq3'})
                    self.assertEqual({item.name for item in p.avoidExercise}, {'Avoid1', 'Avoid2', 'Avoid3'})
                    for patient in ('wrongType', 'missingFact', 'noFavorite'):
                        self.assertEqual(world[EX + patient].recommendedExercise, [])
                        self.assertEqual(world[EX + patient].avoidExercise, [])
                finally:
                    world.close()

    def test_reject_invalid_intensity_and_stale_multi_output(self):
        cat = read_catalog(fixture())
        for key, value in [('intensity', ''), ('intensity', EX + 'Deleted'), ('use_favorites', 'true')]:
            data = r2()
            data['outputs'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                compile_builder_rule(data, cat)
        for outputs in ([], [None], [{'action': 'avoid', 'result': EX + 'Deleted'}], [{'action': 'intensity', 'result': EX + 'Moderate'}]):
            data = r2()
            data['outputs'] = outputs
            with self.assertRaises(ValueError):
                compile_builder_rule(data, cat)

    def test_met_is_derived_on_server(self):
        cat = read_catalog(fixture())
        data = r2()
        expected = compile_builder_rule(data, cat)
        data['outputs'][0].update(met_min='100', met_max='200')
        self.assertEqual(compile_builder_rule(data, cat), expected)
        cat['results']['intensity'].append({'value': EX + 'Unknown', 'label': 'Unknown'})
        data['outputs'][0]['intensity'] = EX + 'Unknown'
        with self.assertRaises(ValueError):
            compile_builder_rule(data, cat)

    def test_legacy_payload_and_literal_labs(self):
        cat = read_catalog(fixture())
        data = {'name': 'Legacy', 'conditions': [{'field': 'ketone', 'op': 'eq', 'value': 'Negative'}], 'action': 'warning', 'result': EX + 'Warning1'}
        compiled = compile_builder_rule(data, cat)
        self.assertIn('ex:hasKetone(?le, "Negative")', compiled['swrl_expression'])
        query, _ = _build_rule_insert_query(**compiled)
        graph = Graph()
        graph.update(query)
        self.assertGreater(len(graph), 0)

    def test_route_saves_all_heads_and_returns_validation_error(self):
        from routes.admin import admin_bp
        app = Flask(__name__, template_folder='../templates', static_folder='../static')
        app.secret_key = 'test'
        app.register_blueprint(admin_bp, url_prefix='/admin')
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id='test', role='admin')
        with patch('routes.admin.get_builder_catalog', return_value=read_catalog(fixture())), patch('routes.admin.add_swrl_rule', return_value={'success': True}) as save:
            self.assertEqual(client.get('/admin/swrl/new').status_code, 200)
            self.assertEqual(client.post('/admin/api/swrl/rules/builder', json=r2()).status_code, 200)
            self.assertEqual(len(save.call_args.kwargs['swrl_expression'].split(' -> ')[1].split(' ^ ')), 8)
            save.reset_mock()
            data = r2()
            data['outputs'][0]['intensity'] = EX + 'Deleted'
            self.assertEqual(client.post('/admin/api/swrl/rules/builder', json=data).status_code, 400)
            save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
