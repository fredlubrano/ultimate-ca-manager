"""
Discovery API Routes v2.0
/api/v2/discovery/* — Certificate network discovery and scanning
"""
from flask import Blueprint, request
from auth.unified import require_auth
from utils.response import success_response, error_response, no_content_response
from services.discovery_service import DiscoveryService
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('discovery_v2', __name__)


def _get_service():
    """Lazy-init to avoid import-time Flask context issues."""
    return DiscoveryService()


# ------------------------------------------------------------------
# Scan endpoints
# ------------------------------------------------------------------

@bp.route('/api/v2/discovery/scan', methods=['POST'])
@require_auth(['admin:system'])
def scan_targets():
    """Scan a list of targets for TLS certificates."""
    try:
        data = request.get_json() or {}
        targets = data.get('targets', [])
        ports = data.get('ports', [443])

        if not targets:
            return error_response("No targets specified", 400)
        if len(targets) > 500:
            return error_response("Maximum 500 targets per scan", 400)

        svc = _get_service()
        results = svc.scan_targets(targets, ports)
        summary = svc.save_results(results)

        return success_response(data={
            'results': results,
            'summary': summary,
        })
    except Exception as e:
        logger.error(f"Discovery scan failed: {e}", exc_info=True)
        return error_response("Scan failed", 500)


@bp.route('/api/v2/discovery/scan-subnet', methods=['POST'])
@require_auth(['admin:system'])
def scan_subnet():
    """Scan a CIDR subnet for TLS certificates."""
    try:
        data = request.get_json() or {}
        subnet = data.get('subnet', '').strip()
        ports = data.get('ports', [443])

        if not subnet:
            return error_response("No subnet specified", 400)

        import ipaddress
        try:
            net = ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            return error_response("Invalid CIDR notation", 400)

        if net.num_addresses > 1024:
            return error_response("Subnet too large (max /22 = 1024 hosts)", 400)

        svc = _get_service()
        results = svc.scan_subnet(subnet, ports)
        summary = svc.save_results(results)

        return success_response(data={
            'results': results,
            'summary': summary,
        })
    except Exception as e:
        logger.error(f"Subnet scan failed: {e}", exc_info=True)
        return error_response("Scan failed", 500)


# ------------------------------------------------------------------
# Read endpoints
# ------------------------------------------------------------------

@bp.route('/api/v2/discovery', methods=['GET'])
@require_auth(['read:certificates'])
def list_discovered():
    """List all discovered certificates."""
    try:
        limit = request.args.get('limit', 500, type=int)
        svc = _get_service()
        data = svc.get_all(limit)
        return success_response(data=data)
    except Exception as e:
        logger.error(f"Failed to list discovered certs: {e}", exc_info=True)
        return error_response("Failed to retrieve discovered certificates", 500)


@bp.route('/api/v2/discovery/unknown', methods=['GET'])
@require_auth(['read:certificates'])
def list_unknown():
    """List certificates not matched in UCM."""
    try:
        svc = _get_service()
        data = svc.get_unknown()
        return success_response(data=data)
    except Exception as e:
        logger.error(f"Failed to list unknown certs: {e}", exc_info=True)
        return error_response("Failed to retrieve unknown certificates", 500)


@bp.route('/api/v2/discovery/expired', methods=['GET'])
@require_auth(['read:certificates'])
def list_expired():
    """List expired discovered certificates."""
    try:
        svc = _get_service()
        data = svc.get_expired()
        return success_response(data=data)
    except Exception as e:
        logger.error(f"Failed to list expired certs: {e}", exc_info=True)
        return error_response("Failed to retrieve expired certificates", 500)


@bp.route('/api/v2/discovery/stats', methods=['GET'])
@require_auth(['read:certificates'])
def get_stats():
    """Get discovery summary statistics."""
    try:
        svc = _get_service()
        stats = svc.get_stats()
        return success_response(data=stats)
    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        return error_response("Failed to retrieve statistics", 500)


# ------------------------------------------------------------------
# Delete endpoints
# ------------------------------------------------------------------

@bp.route('/api/v2/discovery/<int:disc_id>', methods=['DELETE'])
@require_auth(['delete:certificates'])
def delete_discovered(disc_id):
    """Delete a single discovered certificate."""
    try:
        svc = _get_service()
        if not svc.delete(disc_id):
            return error_response("Not found", 404)
        return no_content_response()
    except Exception as e:
        logger.error(f"Failed to delete discovered cert {disc_id}: {e}", exc_info=True)
        return error_response("Failed to delete", 500)


@bp.route('/api/v2/discovery', methods=['DELETE'])
@require_auth(['admin:system'])
def delete_all_discovered():
    """Delete all discovered certificates."""
    try:
        svc = _get_service()
        count = svc.delete_all()
        return success_response(data={'deleted': count}, message=f"Deleted {count} records")
    except Exception as e:
        logger.error(f"Failed to delete all: {e}", exc_info=True)
        return error_response("Failed to delete", 500)
