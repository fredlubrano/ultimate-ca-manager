"""
Protocol URL helper
Provides the base URL for PKI protocol endpoints (CDP, OCSP, EST, SCEP).
Users can configure a separate base URL (e.g. http://) to avoid TLS
verification loops when clients fetch CRLs or OCSP responses.
"""
import os
from flask import request as flask_request
from models import SystemConfig


def get_protocol_base_url():
    """
    Get the base URL for protocol endpoints.
    Priority:
      1. protocol_base_url setting (user-configured)
      2. HTTP_PROTOCOL_PORT env var → http://{hostname}:{port}
      3. Current request's host URL (HTTPS)
    """
    config = SystemConfig.query.filter_by(key='protocol_base_url').first()
    if config and config.value:
        return config.value.rstrip('/')

    http_port = int(os.getenv('HTTP_PROTOCOL_PORT', '0'))
    if http_port > 0:
        hostname = flask_request.host.split(':')[0]
        suffix = '' if http_port == 80 else f':{http_port}'
        return f'http://{hostname}{suffix}'

    return flask_request.host_url.rstrip('/')
