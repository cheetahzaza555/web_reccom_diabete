from dotenv import load_dotenv
load_dotenv()
from flask import Flask
import os
from routes.user import user_bp
from flask_cors import CORS
from routes.auth import auth
from routes.admin import admin_bp

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
if os.getenv("APP_ENV") == "production" and (not app.secret_key or len(app.secret_key) < 32):
    raise RuntimeError("Set SECRET_KEY to a random value of at least 32 characters")
if os.getenv("APP_ENV") == "production" and len(os.getenv("JWT_SECRET_KEY", "")) < 32:
    raise RuntimeError("Set JWT_SECRET_KEY to a random value of at least 32 characters")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
)
if os.getenv("TRUST_PROXY") == "1":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


@app.get('/healthz')
def health():
    return {"status": "ok"}


@app.get('/readyz')
def ready():
    import requests
    from modules.config import GRAPHDB_READ
    try:
        response = requests.get(GRAPHDB_READ, params={"query": "ASK { ?s ?p ?o }"},
                                headers={"Accept": "application/sparql-results+json"}, timeout=5)
        response.raise_for_status()
        if not response.json().get('boolean'):
            return {"status": "database_empty"}, 503
        return {"status": "ready"}
    except (requests.RequestException, ValueError):
        return {"status": "database_unavailable"}, 503

# Scheduled jobs run separately in scheduler.py.
CORS(app)

# ลงทะเบียน Blueprint
app.register_blueprint(auth)
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(admin_bp, url_prefix="/admin")
if os.getenv('LINE_CHANNEL_ACCESS_TOKEN') and os.getenv('LINE_CHANNEL_SECRET'):
    from routes.webhook import webhook_bp
    app.register_blueprint(webhook_bp, url_prefix='/line')

if __name__ == '__main__':
    print("🚀 Starting Flask Server (Powered by GraphDB Semantic Web)...")
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", use_reloader=False, port=5000)
