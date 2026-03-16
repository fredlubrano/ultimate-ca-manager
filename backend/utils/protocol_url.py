"""
Protocol URL helper
Provides the base URL for PKI protocol endpoints (CDP, OCSP, EST, SCEP).
Users can configure a separate base URL (e.g. http://) to avoid TLS
verification loops when clients fetch CRLs or OCSP responses.
"""
import logging
from flask import request as flask_request
from models import SystemConfig

logger = logging.getLogger(__name__)


def get_protocol_base_url():
    """
    Get the base URL for protocol endpoints.
    Priority:
      1. protocol_base_url setting (user-configured explicit URL)
      2. http_protocol_port setting > 0 → http://{hostname}:{port}
      3. Current request's host URL (HTTPS fallback)
    """
    try:
        # 1. Explicit user-configured URL takes priority
        config = SystemConfig.query.filter_by(key='protocol_base_url').first()
        if config and config.value and config.value.strip():
            return config.value.strip().rstrip('/')

        # 2. Auto-generate from HTTP protocol port
        from protocol_http_server import get_http_protocol_port
        http_port = get_http_protocol_port()
        if http_port > 0:
            hostname = flask_request.host.split(':')[0]
            suffix = '' if http_port == 80 else f':{http_port}'
            return f'http://{hostname}{suffix}'
    except Exception as e:
        logger.debug("Protocol URL fallback to request host: %s", e)

    # 3. Fallback to current request URL
    return flask_request.host_url.rstrip('/')
