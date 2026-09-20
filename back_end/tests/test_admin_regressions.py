"""Admin error-path checks; never connect to the application database."""
import unittest
from unittest.mock import patch

from flask import Flask
from rdflib import Graph, Namespace, RDF, RDFS, Literal
from modules.db import admin_repository as repository
from routes.admin import admin_bp


class AdminRegressions(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test-only'
        self.app.register_blueprint(admin_bp, url_prefix='/admin')
        self.app.add_url_rule('/login', endpoint='auth.login_page', view_func=lambda: 'login')
        self.app.add_url_rule('/user/dashboard', endpoint='user.dashboard_page', view_func=lambda: 'user')
        self.client = self.app.test_client()

    def login(self, role='admin'):
        with self.client.session_transaction() as session:
            session.update(user_id='1', role=role)

    def test_access_redirects_and_api_status(self):
        self.assertEqual(self.client.get('/admin/dashboard').location, '/login')
        self.assertEqual(self.client.get('/admin/api/patient/1').status_code, 401)
        self.login('user')
        self.assertEqual(self.client.get('/admin/dashboard').location, '/user/dashboard')
        self.assertEqual(self.client.get('/admin/api/patient/1').status_code, 403)

    def test_category_delete_reports_actual_result(self):
        self.login()
        for success, status in [(True, 200), (False, 400)]:
            with patch('routes.admin.delete_category_from_ontology', return_value={'success': success, 'message': 'result'}):
                response = self.client.post('/admin/api/categories/delete', json={'category_id': 'Walking'})
                self.assertEqual(response.status_code, status)
                self.assertIs(response.json['success'], success)

    def test_invalid_exercise_edit_never_deletes_old_data(self):
        self.login()
        with patch('routes.admin.delete_exercise_from_ontology') as delete, patch.object(repository, 'SPARQLWrapper') as client:
            response = self.client.post('/admin/exercises/update', json={'id': '17101', 'name': 'Walk', 'type': 'Walking', 'mets': 'invalid'})
            self.assertEqual(response.status_code, 400)
            delete.assert_not_called()
            client.assert_not_called()

    def test_exercise_update_preserves_links_and_escapes_text(self):
        ex = Namespace('http://example.org/diabetes#')
        graph = Graph()
        graph.add((ex.Walking, RDFS.subClassOf, ex.Exercise))
        graph.add((ex.Running, RDFS.subClassOf, ex.Exercise))
        graph.add((ex['17101'], RDF.type, ex.Exercise))
        graph.add((ex['17101'], RDF.type, ex.Walking))
        graph.add((ex['17101'], RDFS.label, Literal('Old')))
        graph.add((ex['17101'], ex.hasKindOfExercise, ex.Walking))
        graph.add((ex.Patient1, ex.recommendedExercise, ex['17101']))
        graph.add((ex['17101'], ex.customNote, Literal('keep')))
        name = 'Run "test"\nwith a quote'
        with patch.object(repository, 'SPARQLWrapper') as client:
            result = repository.insert_exercise_to_ontology_v2('17101', name, 'Running', '4.5', 'video')
            self.assertTrue(result['success'])
            client.return_value.query.assert_called_once()
            graph.update(client.return_value.setQuery.call_args.args[0])
        self.assertEqual(list(graph.objects(ex['17101'], RDFS.label)), [Literal(name)])
        self.assertNotIn((ex['17101'], RDF.type, ex.Walking), graph)
        self.assertIn((ex['17101'], RDF.type, ex.Running), graph)
        self.assertIn((ex.Patient1, ex.recommendedExercise, ex['17101']), graph)
        self.assertIn((ex['17101'], ex.customNote, Literal('keep')), graph)


if __name__ == '__main__':
    unittest.main()
