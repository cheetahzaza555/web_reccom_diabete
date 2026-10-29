"""Application-owned headers; proxy must not append a second CSP/HSTS policy."""
import os
import secrets
from flask import g, request


def install_security_headers(app):
    @app.before_request
    def make_nonce():
        g.csp_nonce = secrets.token_urlsafe(24)

    @app.context_processor
    def template_nonce():
        return {'csp_nonce': getattr(g, 'csp_nonce', '')}

    @app.after_request
    def protect_response(response):
        # แก้ Low: Big Redirect Detected โดยล้าง response body เมื่อเป็น redirect 3xx ป้องกันข้อมูลรั่วไหล
        if 300 <= response.status_code < 400:
            response.data = b""

        nonce = getattr(g, 'csp_nonce', '')
        policy = [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'self'",
            "form-action 'self' https://accounts.google.com",
            f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://accounts.google.com",
            "script-src-attr 'unsafe-inline'",
            f"style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com https://cdn.jsdelivr.net https://accounts.google.com",
            "style-src-attr 'unsafe-inline'",
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net data:",
            "img-src 'self' data: blob: https://images.unsplash.com https://img.youtube.com https://*.googleusercontent.com https://lh3.googleusercontent.com",
            "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com",
            "frame-src 'self' https://accounts.google.com https://www.youtube.com https://www.youtube-nocookie.com",
            "media-src 'self' blob:",
        ]
        response.headers['Content-Security-Policy'] = '; '.join(policy)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(self), geolocation=()'

        # Strict-Transport-Security (1 ปี พร้อม preload)
        if request.is_secure or os.getenv("APP_ENV") == "production" or os.getenv("TRUST_PROXY") == "1":
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        # Cache-Control ป้องกัน Browser แคชหน้า Auth/ข้อมูลส่วนบุคคล
        if response.mimetype == 'text/html' or request.path.startswith(("/login", "/register", "/admin", "/user", "/api", "/auth")):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'

        return response
