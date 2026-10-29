"""Application-owned headers; proxy must not append a second CSP/HSTS policy."""
import secrets
from flask import g, request


def install_security_headers(app):
    @app.before_request
    def make_nonce():
        g.csp_nonce = secrets.token_urlsafe(24)

    @app.context_processor
    def template_nonce():
        return {'csp_nonce': g.csp_nonce}

    @app.after_request
    def protect_response(response):
        nonce = g.csp_nonce
        policy = [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'self'",
            "form-action 'self' https://accounts.google.com",
            f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://accounts.google.com",
            # Legacy onclick/onchange handlers need migration before this becomes 'none'.
            "script-src-attr 'unsafe-inline'",
            f"style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com https://cdn.jsdelivr.net https://accounts.google.com",
            # Existing templates and UI libraries still use style attributes.
            "style-src-attr 'unsafe-inline'",
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net data:",
            "img-src 'self' data: blob: https://images.unsplash.com https://img.youtube.com",
            "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com",
            "frame-src 'self' https://accounts.google.com https://www.youtube.com https://www.youtube-nocookie.com",
            "media-src 'self' blob:",
        ]
        response.headers['Content-Security-Policy'] = '; '.join(policy)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(self), geolocation=()'
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'no-store'
        return response
