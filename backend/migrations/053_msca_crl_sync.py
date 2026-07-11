"""Migration 053: CRL-based revocation sync for Microsoft CA connections (#185).

Adds to ``microsoft_cas``:
- ``crl_sync_enabled`` — opt-in flag for the periodic CRL revocation sync
- ``crl_url`` — optional explicit CRL URL (else derived from issued certs' CDP)
- ``last_crl_sync_at`` / ``last_crl_sync_result`` — status of the last sync run
"""
import logging
import sqlite3

logger = logging.getLogger(__name__)
pg_compatible = True

_COLUMNS_SQLITE = [
    ("crl_sync_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
    ("crl_url", "TEXT"),
    ("last_crl_sync_at", "DATETIME"),
    ("last_crl_sync_result", "VARCHAR(500)"),
]

_COLUMNS_PG = [
    ("crl_sync_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("crl_url", "TEXT"),
    ("last_crl_sync_at", "TIMESTAMP"),
    ("last_crl_sync_result", "VARCHAR(500)"),
]


def _upgrade_sqlite(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='microsoft_cas'"
    )
    if not cur.fetchone():
        logger.info("[053] microsoft_cas absent, skipping")
        return
    existing = {r[1] for r in conn.execute("PRAGMA table_info(microsoft_cas)").fetchall()}
    for name, ddl in _COLUMNS_SQLITE:
        if name not in existing:
            conn.execute(f"ALTER TABLE microsoft_cas ADD COLUMN {name} {ddl}")
    conn.commit()
    logger.info("[053] msca CRL sync columns added (SQLite)")


def _upgrade_pg(conn):
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if 'microsoft_cas' not in insp.get_table_names():
        logger.info("[053] microsoft_cas absent, skipping")
        return
    existing = {c['name'] for c in insp.get_columns('microsoft_cas')}
    for name, ddl in _COLUMNS_PG:
        if name not in existing:
            conn.execute(text(f"ALTER TABLE microsoft_cas ADD COLUMN {name} {ddl}"))
    logger.info("[053] msca CRL sync columns added (PostgreSQL)")


def upgrade(conn):
    if isinstance(conn, sqlite3.Connection):
        _upgrade_sqlite(conn)
    else:
        _upgrade_pg(conn)


def downgrade(conn):
    names = [name for name, _ in _COLUMNS_SQLITE]
    if isinstance(conn, sqlite3.Connection):
        for name in names:
            try:
                conn.execute(f"ALTER TABLE microsoft_cas DROP COLUMN {name}")
            except sqlite3.OperationalError:
                pass
        conn.commit()
    else:
        from sqlalchemy import text
        for name in names:
            conn.execute(text(f"ALTER TABLE microsoft_cas DROP COLUMN IF EXISTS {name}"))
