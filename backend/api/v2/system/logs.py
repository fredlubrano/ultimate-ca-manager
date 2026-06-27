"""System diagnostic log bundle download.

Returns a ZIP of the most relevant UCM logs (ucm.log, error.log, access.log,
the last lines of the systemd journal when running under systemd) plus a small
secret-free ``system.txt`` diagnostic. Sensitive tokens are redacted before
packaging. Admin-only (``admin:system``).
"""
from . import bp

import logging

from auth.unified import require_auth
from flask import Response
from services.audit_service import AuditService
from services.log_bundle import build_bundle, bundle_filename
from utils.response import error_response
from utils.trusted_proxy import client_ip

logger = logging.getLogger(__name__)


@bp.route('/api/v2/system/logs/bundle', methods=['GET'])
@require_auth(['admin:system'])
def download_log_bundle():
    """Download a diagnostic log bundle (ZIP)."""
    try:
        data = build_bundle()
    except Exception as exc:  # noqa: BLE001
        logger.error('Log bundle build failed: %s', exc)
        return error_response('Failed to build log bundle', 500)

    AuditService.log_action(
        action='log_bundle_downloaded',
        resource_type='system',
        resource_name='Log bundle',
        details=f'Log bundle downloaded from {client_ip()}',
        success=True,
    )

    return Response(
        data,
        mimetype='application/zip',
        headers={
            'Content-Disposition': f'attachment; filename="{bundle_filename()}"',
            'Cache-Control': 'no-store, no-cache, must-revalidate, private',
            'Pragma': 'no-cache',
            'X-Content-Type-Options': 'nosniff',
        },
    )
