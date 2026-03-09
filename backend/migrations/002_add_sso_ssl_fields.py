"""
Migration 002: Add SSL verification fields to SSO providers

Adds per-protocol SSL verification toggle and optional CA bundle
for OAuth2, SAML, and LDAP connections. Fixes GitHub issue #33 where
users with self-signed or private CA certificates cannot connect to
OIDC/SAML/LDAP providers.
"""
import logging

logger = logging.getLogger(__name__)


def upgrade(conn):
    """Add SSL verification fields to pro_sso_providers"""
    columns = [
        ('oauth2_verify_ssl', 'BOOLEAN DEFAULT 1'),
        ('oauth2_ca_bundle', 'TEXT'),
        ('saml_verify_ssl', 'BOOLEAN DEFAULT 1'),
        ('saml_ca_bundle', 'TEXT'),
        ('ldap_verify_ssl', 'BOOLEAN DEFAULT 1'),
        ('ldap_ca_bundle', 'TEXT'),
    ]

    for col_name, col_type in columns:
        try:
            conn.execute(f"ALTER TABLE pro_sso_providers ADD COLUMN {col_name} {col_type}")
            logger.info(f"Added column {col_name} to pro_sso_providers")
        except Exception as e:
            if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                logger.debug(f"Column {col_name} already exists, skipping")
            else:
                raise

    conn.commit()
    logger.info("Migration 002 complete: SSO SSL fields added")


def downgrade(conn):
    """SQLite doesn't support DROP COLUMN easily, so this is a no-op.
    The columns will be ignored if not used."""
    logger.info("Migration 002 downgrade: no-op (SQLite limitation)")
