"""Offline checks: no database, email or LINE calls. Run inside the built image."""
import os
import subprocess
from unittest.mock import patch

os.environ.update(APP_ENV='production', SECRET_KEY='test-only-' * 5,
                  JWT_SECRET_KEY='jwt-test-only-' * 4,
                  LINE_CHANNEL_ACCESS_TOKEN='', LINE_CHANNEL_SECRET='',
                  SESSION_COOKIE_SECURE='1', TRUST_PROXY='1')

from app import app
from werkzeug.security import generate_password_hash

client = app.test_client()
assert client.get('/healthz').status_code == 200
for path in ['/force-run-reschedule', '/force-run-reminder']:
    assert client.get(path).status_code == 404
assert not app.debug
with patch('requests.get') as get:
    get.return_value.json.return_value = {'boolean': True}
    assert client.get('/readyz').status_code == 200
    get.return_value.json.return_value = {'boolean': False}
    assert client.get('/readyz').status_code == 503
with patch('routes.auth.get_user_for_login', return_value={
    'patient_id': 'deploy_test', 'username': 'test', 'role': 'user',
    'password_hash': generate_password_hash('test-password'),
}):
    response = client.post('/api/login', json={'username': 'test', 'password': 'test-password'},
                           base_url='https://test.example.org')
    assert response.status_code == 200, response.status_code
    assert response.json.get('token')
    cookie = response.headers['Set-Cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
subprocess.run(['python', '-m', 'pip', 'check'], check=True)
subprocess.run(['java', '-version'], check=True)

from owlready2 import World, Thing, Imp, sync_reasoner_pellet
world = World()
onto = world.get_ontology('http://example.org/deploy-check#')
with onto:
    class Input(Thing): pass
    class Output(Thing): pass
    subject = Input('test')
    rule = Imp()
    rule.set_as_rule('Input(?x) -> Output(?x)')
sync_reasoner_pellet(world, infer_property_values=True, infer_data_property_values=True)
assert subject in onto.Output.instances()
world.close()
print('PASS: app, JWT login, cookies, readiness, dependencies and actual Pellet reasoning')
