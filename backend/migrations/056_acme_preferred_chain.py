"""Migration 056: preferred_chain on acme_client_accounts (RFC 8555 alternate chains)."""
import logging
import sqlite3

logger = logging.getLogger(__name__)
pg_compatible = True


def _column_exists_sqlite(conn, table, column):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _upgrade_sqlite(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='acme_client_accounts'"
    )
    if not cur.fetchone():
        logger.info("[056] acme_client_accounts absent, skipping")
        return

    if not _column_exists_sqlite(conn, 'acme_client_accounts', 'preferred_chain'):
        conn.execute(
            "ALTER TABLE acme_client_accounts ADD COLUMN preferred_chain VARCHAR(255)"
        )
        logger.info("[056] added acme_client_accounts.preferred_chain")


def _downgrade_sqlite(conn):
    pass


def upgrade(conn):
    if isinstance(conn, sqlite3.Connection):
        _upgrade_sqlite(conn)
        return

    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if 'acme_client_accounts' not in insp.get_table_names():
        logger.info("[056] acme_client_accounts absent, skipping")
        return

    existing = {c['name'] for c in insp.get_columns('acme_client_accounts')}
    if 'preferred_chain' not in existing:
        conn.execute(text(
            'ALTER TABLE acme_client_accounts ADD COLUMN preferred_chain VARCHAR(255)'
        ))
        logger.info("[056] added acme_client_accounts.preferred_chain")


def downgrade(conn):
    if isinstance(conn, sqlite3.Connection):
        _downgrade_sqlite(conn)
