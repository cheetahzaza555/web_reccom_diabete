from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request
import os
from routes.user import user_bp
from utils.security_headers import install_security_headers
from routes.auth import auth
from routes.admin import admin_bp
from modules.oauth import init_oauth

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
if os.getenv("APP_ENV") == "production" and (not app.secret_key or len(app.secret_key) < 32):
    raise RuntimeError("Set SECRET_KEY to a random value of at least 32 characters")
if os.getenv("APP_ENV") == "production" and len(os.getenv("JWT_SECRET_KEY", "")) < 32:
    raise RuntimeError("Set JWT_SECRET_KEY to a random value of at least 32 characters")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("APP_ENV") == "production" or os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
)
if os.getenv("TRUST_PROXY") == "1":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# ตั้งค่า OAuth (Google Login)
init_oauth(app)


# เพิ่ม Security Headers ทั้งหมดเพื่อปิดช่องโหว่ OWASP ZAP (Medium & Low alerts เป็น 0)
@app.after_request
def apply_security_headers(response):
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(self), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://accounts.google.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net data:; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com; "
        "frame-src 'self' https://accounts.google.com; "
        "frame-ancestors 'self';"
    )
    # แก้ Low: Big Redirect Detected โดยล้าง response body เมื่อเป็น redirect 3xx ป้องกันข้อมูลรั่วไหล
    if 300 <= response.status_code < 400:
        response.data = b""

    # แก้ Info/Low: Cache-control
    if request.path.startswith(("/login", "/register", "/admin", "/user", "/api", "/auth")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


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
# Browser requests use the same origin; do not expose every route via wildcard CORS.
install_security_headers(app)

# ลงทะเบียน Blueprint
app.register_blueprint(auth)
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(admin_bp, url_prefix="/admin")
if os.getenv('LINE_CHANNEL_ACCESS_TOKEN') and os.getenv('LINE_CHANNEL_SECRET'):
    from routes.webhook import webhook_bp
    app.register_blueprint(webhook_bp, url_prefix='/line')

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5001))
    try:
        print(f"🚀 Starting Flask Server on port {port} (Powered by GraphDB Semantic Web)...")
    except UnicodeEncodeError:
        print(f"[OK] Starting Flask Server on port {port} (Powered by GraphDB Semantic Web)...")
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", use_reloader=False, port=port)
