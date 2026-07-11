"""Migration 055: CA inventory sync for Microsoft CA connections (#185 phase B).

Adds to ``microsoft_cas`` the state for the inventory sync that imports
certificates issued directly on the Windows CA (via the WinRM admin channel)
into UCM, plus the high-water mark for incremental scans.
"""
import logging
import sqlite3

logger = logging.getLogger(__name__)
pg_compatible = True

_COLUMNS_SQLITE = [
    ("inventory_sync_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
    ("last_inventory_sync_at", "DATETIME"),
    ("last_inventory_sync_result", "VARCHAR(500)"),
    ("last_synced_request_id", "INTEGER NOT NULL DEFAULT 0"),
]

_COLUMNS_PG = [
    ("inventory_sync_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("last_inventory_sync_at", "TIMESTAMP"),
    ("last_inventory_sync_result", "VARCHAR(500)"),
    ("last_synced_request_id", "INTEGER NOT NULL DEFAULT 0"),
]


def _upgrade_sqlite(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='microsoft_cas'"
    )
    if not cur.fetchone():
        logger.info("[055] microsoft_cas absent, skipping")
        return
    existing = {r[1] for r in conn.execute("PRAGMA table_info(microsoft_cas)").fetchall()}
    for name, ddl in _COLUMNS_SQLITE:
        if name not in existing:
            conn.execute(f"ALTER TABLE microsoft_cas ADD COLUMN {name} {ddl}")
    conn.commit()
    logger.info("[055] msca inventory columns added (SQLite)")


def _upgrade_pg(conn):
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if 'microsoft_cas' not in insp.get_table_names():
        logger.info("[055] microsoft_cas absent, skipping")
        return
    existing = {c['name'] for c in insp.get_columns('microsoft_cas')}
    for name, ddl in _COLUMNS_PG:
        if name not in existing:
            conn.execute(text(f"ALTER TABLE microsoft_cas ADD COLUMN {name} {ddl}"))
    logger.info("[055] msca inventory columns added (PostgreSQL)")


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
