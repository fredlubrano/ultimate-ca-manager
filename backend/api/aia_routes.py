"""
AIA CA Issuers Routes — Public CA certificate download
Serves CA certificates for AIA CA Issuers extension (RFC 5280 §4.2.2.1).
Supports both refid-based (preferred) and legacy numeric ID-based URLs.
"""
import base64
from flask import Blueprint, Response, abort
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding
import logging

from models import CA

logger = logging.getLogger(__name__)

aia_bp = Blueprint('aia', __name__)


def _resolve_ca(ca_ref):
    """Resolve CA by refid (UUID) or legacy numeric ID"""
    ca = CA.query.filter_by(refid=ca_ref).first()
    if ca:
        return ca
    try:
        ca_id_int = int(ca_ref)
        return CA.query.get(ca_id_int)
    except (ValueError, TypeError):
        return None


@aia_bp.route('/<ca_ref>.cer')
def get_ca_cert_der(ca_ref):
    """
    Serve CA certificate in DER format (application/pkix-cert).
    This is the standard format for AIA CA Issuers (RFC 5280).
    """
    ca = _resolve_ca(ca_ref)
    if not ca or not ca.crt:
        abort(404)

    try:
        cert_pem = base64.b64decode(ca.crt)
        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        cert_der = cert.public_bytes(Encoding.DER)
    except Exception as e:
        logger.error(f"AIA: failed to encode CA {ca_ref} certificate: {e}")
        abort(500)

    return Response(
        cert_der,
        status=200,
        mimetype='application/pkix-cert',
        headers={
            'Content-Disposition': f'inline; filename="{ca.refid}.cer"',
            'Cache-Control': 'public, max-age=86400, must-revalidate',
        }
    )


@aia_bp.route('/<ca_ref>.pem')
def get_ca_cert_pem(ca_ref):
    """Serve CA certificate in PEM format."""
    ca = _resolve_ca(ca_ref)
    if not ca or not ca.crt:
        abort(404)

    try:
        cert_pem = base64.b64decode(ca.crt)
        # Validate it's a proper PEM certificate
        x509.load_pem_x509_certificate(cert_pem, default_backend())
    except Exception as e:
        logger.error(f"AIA: failed to load CA {ca_ref} certificate: {e}")
        abort(500)

    return Response(
        cert_pem,
        status=200,
        mimetype='application/x-pem-file',
        headers={
            'Content-Disposition': f'inline; filename="{ca.refid}.pem"',
            'Cache-Control': 'public, max-age=86400, must-revalidate',
        }
    )
