"""
Discovery API v2
Scan profiles, async scanning, results, history.
"""
import ipaddress
import logging

from flask import Blueprint, request, current_app
from auth.unified import require_auth
from utils.response import success_response, error_response, created_response, no_content_response

logger = logging.getLogger(__name__)

bp = Blueprint('discovery', __name__)

_service = None


def _get_service():
    global _service
    if _service is None:
        from services.discovery_service import DiscoveryService
        _service = DiscoveryService()
    return _service


# ==================== Scan Profiles ====================

@bp.route('/api/v2/discovery/profiles', methods=['GET'])
@require_auth(['read:certificates'])
def list_profiles():
    """List all scan profiles."""
    svc = _get_service()
    return success_response(data=svc.get_profiles())


@bp.route('/api/v2/discovery/profiles', methods=['POST'])
@require_auth(['admin:system'])
def create_profile():
    """Create a new scan profile."""
    data = request.get_json()
    if not data or not data.get('name'):
        return error_response("Profile name is required", 400)
    if not data.get('targets') or not isinstance(data['targets'], list):
        return error_response("Targets must be a non-empty list", 400)
    if len(data['targets']) > 1000:
        return error_response("Maximum 1000 targets per profile", 400)
    svc = _get_service()
    try:
        profile = svc.create_profile(data)
        return created_response(data=profile, message="Profile created")
    except Exception as e:
        if 'UNIQUE' in str(e):
            return error_response("A profile with this name already exists", 409)
        logger.error(f"Failed to create profile: {e}")
        return error_response("Failed to create profile", 500)


@bp.route('/api/v2/discovery/profiles/<int:profile_id>', methods=['GET'])
@require_auth(['read:certificates'])
def get_profile(profile_id):
    """Get a single scan profile."""
    svc = _get_service()
    profile = svc.get_profile(profile_id)
    if not profile:
        return error_response("Profile not found", 404)
    return success_response(data=profile)


@bp.route('/api/v2/discovery/profiles/<int:profile_id>', methods=['PUT'])
@require_auth(['admin:system'])
def update_profile(profile_id):
    """Update a scan profile."""
    data = request.get_json()
    if not data:
        return error_response("No data provided", 400)
    svc = _get_service()
    profile = svc.update_profile(profile_id, data)
    if not profile:
        return error_response("Profile not found", 404)
    return success_response(data=profile, message="Profile updated")


@bp.route('/api/v2/discovery/profiles/<int:profile_id>', methods=['DELETE'])
@require_auth(['admin:system'])
def delete_profile(profile_id):
    """Delete a scan profile."""
    svc = _get_service()
    if not svc.delete_profile(profile_id):
        return error_response("Profile not found", 404)
    return no_content_response()


# ==================== Scanning ====================

@bp.route('/api/v2/discovery/profiles/<int:profile_id>/scan', methods=['POST'])
@require_auth(['admin:system'])
def scan_profile(profile_id):
    """Trigger a scan for a profile. Returns scan run ID."""
    svc = _get_service()
    profile = svc.get_profile(profile_id)
    if not profile:
        return error_response("Profile not found", 404)

    from flask import g
    username = g.current_user.username if hasattr(g, 'current_user') else 'unknown'

    run_id = svc.start_scan(
        targets=profile['targets'],
        ports=profile['ports'],
        profile_id=profile_id,
        triggered_by='manual',
        triggered_by_user=username,
        app=current_app._get_current_object(),
    )
    return success_response(data={'scan_run_id': run_id}, message="Scan started")


@bp.route('/api/v2/discovery/scan', methods=['POST'])
@require_auth(['admin:system'])
def ad_hoc_scan():
    """Ad-hoc scan without a saved profile."""
    data = request.get_json()
    if not data:
        return error_response("No data provided", 400)

    targets = data.get('targets', [])
    subnet = data.get('subnet')
    ports = data.get('ports', [443])

    if not targets and not subnet:
        return error_response("Provide either 'targets' or 'subnet'", 400)
    if targets and len(targets) > 500:
        return error_response("Maximum 500 targets per ad-hoc scan", 400)

    if subnet:
        try:
            net = ipaddress.ip_network(subnet, strict=False)
            if net.prefixlen < 22:
                return error_response("Subnet too large (max /22)", 400)
        except ValueError as e:
            return error_response(f"Invalid subnet: {e}", 400)

    svc = _get_service()
    from flask import g
    username = g.current_user.username if hasattr(g, 'current_user') else 'unknown'

    if subnet:
        run_id = svc.start_subnet_scan(
            cidr=subnet, ports=ports,
            triggered_by='manual', triggered_by_user=username,
            app=current_app._get_current_object(),
        )
    else:
        run_id = svc.start_scan(
            targets=targets, ports=ports,
            triggered_by='manual', triggered_by_user=username,
            app=current_app._get_current_object(),
        )

    return success_response(data={'scan_run_id': run_id}, message="Scan started")


# ==================== Scan History ====================

@bp.route('/api/v2/discovery/runs', methods=['GET'])
@require_auth(['read:certificates'])
def list_runs():
    """List scan run history."""
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))
    profile_id = request.args.get('profile_id', type=int)
    svc = _get_service()
    items, total = svc.get_runs(limit=limit, offset=offset, profile_id=profile_id)
    return success_response(data={'items': items, 'total': total})


@bp.route('/api/v2/discovery/runs/<int:run_id>', methods=['GET'])
@require_auth(['read:certificates'])
def get_run(run_id):
    """Get details of a single scan run."""
    svc = _get_service()
    run = svc.get_run(run_id)
    if not run:
        return error_response("Scan run not found", 404)
    return success_response(data=run)


# ==================== Results ====================

@bp.route('/api/v2/discovery', methods=['GET'])
@require_auth(['read:certificates'])
def list_discovered():
    """List discovered certificates with pagination and filtering."""
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))
    profile_id = request.args.get('profile_id', type=int)
    status = request.args.get('status')
    svc = _get_service()
    items, total = svc.get_all(limit=limit, offset=offset,
                               profile_id=profile_id, status=status)
    return success_response(data={'items': items, 'total': total})


@bp.route('/api/v2/discovery/stats', methods=['GET'])
@require_auth(['read:certificates'])
def get_stats():
    """Get discovery statistics."""
    profile_id = request.args.get('profile_id', type=int)
    svc = _get_service()
    return success_response(data=svc.get_stats(profile_id=profile_id))


@bp.route('/api/v2/discovery/<int:disc_id>', methods=['DELETE'])
@require_auth(['delete:certificates'])
def delete_discovered(disc_id):
    """Delete a single discovered certificate."""
    svc = _get_service()
    if not svc.delete(disc_id):
        return error_response("Not found", 404)
    return no_content_response()


@bp.route('/api/v2/discovery', methods=['DELETE'])
@require_auth(['admin:system'])
def delete_all_discovered():
    """Delete all discovered certificates."""
    profile_id = request.args.get('profile_id', type=int)
    svc = _get_service()
    count = svc.delete_all(profile_id=profile_id)
    return success_response(data={'deleted': count}, message=f"Deleted {count} records")
