"""
Request validation decorators.
"""

import functools
import logging
from flask import request, g

from utils.response import error_response

logger = logging.getLogger(__name__)


def require_json_body(fn):
    """
    Decorator that ensures the request has a valid JSON body.

    Sets g.json_data with the parsed body. Returns HTTP 400 if
    Content-Type is not application/json or body cannot be parsed.

    Usage:
        @bp.route('/things', methods=['POST'])
        @require_auth(['write:things'])
        @require_json_body
        def create_thing():
            data = g.json_data
            ...
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        data = request.get_json(silent=True)
        if data is None:
            return error_response('Request body must be valid JSON', 400)
        g.json_data = data
        return fn(*args, **kwargs)
    return wrapper
