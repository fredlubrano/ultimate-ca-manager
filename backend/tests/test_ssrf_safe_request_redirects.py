"""Regression: safe_request_* must not follow redirects into forbidden targets.

DNS pinning alone is insufficient: requests follows redirects by default, and
a hop to 127.0.0.1 / 169.254.169.254 would previously bypass the guard.
"""
import http.server
import socket
import socketserver
import threading

import pytest

from utils.ssrf_protection import (
    safe_request_get,
    safe_request_post,
    validate_url_not_cloud_metadata,
)


def _local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    finally:
        s.close()


class _SilentHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _serve(handler_cls):
    ip = _local_ip()
    httpd = socketserver.TCPServer((ip, 0), handler_cls)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, ip, port


def test_safe_request_post_blocks_redirect_to_loopback():
    """Attacker host passes the guard; Location: http://127.0.0.1 must raise."""

    class Victim(_SilentHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'INTERNAL')

        def do_POST(self):
            self.do_GET()

    victim, _, victim_port = _serve(Victim)

    class Redirector(_SilentHandler):
        def do_POST(self):
            length = int(self.headers.get('Content-Length', 0))
            if length:
                self.rfile.read(length)
            self.send_response(302)
            self.send_header('Location', f'http://127.0.0.1:{victim_port}/secret')
            self.end_headers()

    redir, ip, redir_port = _serve(Redirector)
    try:
        url = f'http://{ip}:{redir_port}/hook'
        validate_url_not_cloud_metadata(url)  # initial URL is allowed
        with pytest.raises(ValueError, match='loopback'):
            safe_request_post(url, data=b'{}', timeout=5)
    finally:
        redir.shutdown()
        victim.shutdown()


def test_safe_request_get_blocks_redirect_to_metadata_literal():
    class Redirector(_SilentHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header('Location', 'http://169.254.169.254/latest/meta-data/')
            self.end_headers()

    redir, ip, redir_port = _serve(Redirector)
    try:
        url = f'http://{ip}:{redir_port}/dir'
        with pytest.raises(ValueError, match='metadata|loopback'):
            safe_request_get(url, timeout=5)
    finally:
        redir.shutdown()


def test_safe_request_get_follows_safe_redirect():
    class Final(_SilentHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK-SAFE')

    final, ip, final_port = _serve(Final)

    class Redirector(_SilentHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header('Location', f'http://{ip}:{final_port}/ok')
            self.end_headers()

    redir, _, redir_port = _serve(Redirector)
    try:
        resp = safe_request_get(f'http://{ip}:{redir_port}/start', timeout=5)
        assert resp.status_code == 200
        assert resp.text == 'OK-SAFE'
        assert f'{final_port}' in resp.url
    finally:
        redir.shutdown()
        final.shutdown()
