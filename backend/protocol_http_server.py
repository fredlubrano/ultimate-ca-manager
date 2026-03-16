"""
Protocol HTTP Server
Lightweight HTTP-only server for CDP/OCSP endpoints.
Avoids TLS certificate verification loops when clients fetch CRLs.

Started automatically when HTTP_PROTOCOL_PORT is set (e.g. 8080).
Only serves /cdp/ and /ocsp endpoints — all other paths return 404.
"""


class ProtocolOnlyMiddleware:
    """WSGI middleware that restricts access to protocol endpoints only."""

    ALLOWED_PREFIXES = ('/cdp/', '/ocsp')

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if any(path.startswith(p) for p in self.ALLOWED_PREFIXES):
            return self.app(environ, start_response)
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'Only CDP/OCSP endpoints are available on this port']
