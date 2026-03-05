"""
Migration 001: Fix DN format in certificates table

Certificates created before this fix stored subject/issuer using Python's
verbose OID names (commonName, countryName, stateOrProvinceName, etc.)
instead of RFC 4514 abbreviations (CN, C, ST, etc.).

This migration re-parses the stored PEM certificate and updates
subject/issuer fields to use rfc4514_string().
"""
import base64
import logging

logger = logging.getLogger(__name__)

# Verbose OID names that indicate the old broken format
VERBOSE_NAMES = [
    'commonName', 'countryName', 'stateOrProvinceName',
    'localityName', 'organizationName', 'organizationalUnitName',
    'emailAddress', 'domainComponent', 'serialNumber',
]


def _needs_fix(value):
    """Check if a subject/issuer string uses verbose OID names."""
    if not value:
        return False
    return any(name + '=' in value for name in VERBOSE_NAMES)


def upgrade(conn):
    from cryptography import x509

    cursor = conn.execute(
        "SELECT id, crt, subject, issuer FROM certificates"
    )
    rows = cursor.fetchall()
    fixed = 0

    for row in rows:
        cert_id, crt_b64, subject, issuer = row
        if not _needs_fix(subject) and not _needs_fix(issuer):
            continue
        if not crt_b64:
            logger.warning(f"Migration 001: cert {cert_id} has bad DN but no PEM, skipping")
            continue
        try:
            cert_pem = base64.b64decode(crt_b64)
            cert = x509.load_pem_x509_certificate(cert_pem)
            new_subject = cert.subject.rfc4514_string()
            new_issuer = cert.issuer.rfc4514_string()
            conn.execute(
                "UPDATE certificates SET subject = ?, issuer = ? WHERE id = ?",
                (new_subject, new_issuer, cert_id)
            )
            fixed += 1
            logger.info(f"Migration 001: fixed DN for cert {cert_id}")
        except Exception as e:
            logger.error(f"Migration 001: failed to fix cert {cert_id}: {e}")

    if fixed:
        logger.info(f"Migration 001: fixed {fixed} certificate(s) with verbose DN format")
    conn.commit()


def downgrade(conn):
    pass  # Cannot revert to broken format
