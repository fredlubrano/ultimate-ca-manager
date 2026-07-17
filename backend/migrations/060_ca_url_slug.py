"""Migration 060: opt-in named protocol URLs per CA (discussion #207).

Adds certificate_authorities.url_slug — immutable, unique slug used instead
of the refid in CDP/OCSP/AIA URL paths when the CA was created with
"named URLs" enabled. NULL = refid-based URLs (default, unchanged).
"""
import logging
import sqlite3

logger = logging.getLogger(__name__)
pg_compatible = True


def _upgrade_sqlite(conn):
    cur = conn.execute("PRAGMA table_info(certificate_authorities)")
    existing = {row[1] for row in cur.fetchall()}
    if 'url_slug' not in existing:
        conn.execute(
            "ALTER TABLE certificate_authorities ADD COLUMN url_slug VARCHAR(64)"
        )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_cas_url_slug "
        "ON certificate_authorities(url_slug)"
    )
    conn.commit()
    logger.info("[060] added url_slug to certificate_authorities (SQLite)")


def _upgrade_pg(conn):
    from sqlalchemy import text
    conn.execute(text(
        "ALTER TABLE certificate_authorities ADD COLUMN IF NOT EXISTS url_slug VARCHAR(64)"
    ))
    conn.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_cas_url_slug "
        "ON certificate_authorities(url_slug)"
    ))
    logger.info("[060] added url_slug to certificate_authorities (PostgreSQL)")


def upgrade(conn):
    if isinstance(conn, sqlite3.Connection):
        _upgrade_sqlite(conn)
    else:
        _upgrade_pg(conn)


def downgrade(conn):
    if isinstance(conn, sqlite3.Connection):
        try:
            conn.execute("DROP INDEX IF EXISTS ix_cas_url_slug")
            conn.execute("ALTER TABLE certificate_authorities DROP COLUMN url_slug")
            conn.commit()
        except Exception:
            pass
    else:
        from sqlalchemy import text
        conn.execute(text("DROP INDEX IF EXISTS ix_cas_url_slug"))
        conn.execute(text(
            "ALTER TABLE certificate_authorities DROP COLUMN IF EXISTS url_slug"
        ))
