"""
Migration 028: scope SCEP requests by CA

RFC 8894 §3.2.1.1 defines transactionID as SHA-256 of the requester's public
key. The same key (= same transactionID) may legitimately enroll against
different CAs hosted on the same UCM instance, so transaction_id alone cannot
be the natural key.

Changes:
  * adds ``scep_requests.ca_refid`` (FK to ``certificate_authorities.refid``)
  * drops the unique index on ``transaction_id`` alone
  * adds a composite unique constraint on ``(transaction_id, ca_refid)``

Existing rows are backfilled with the CA currently configured for SCEP
(``SystemConfig['scep_ca_id']``) so the new NOT-NULL constraint can apply.

Multi-backend convention: runs on both SQLite and PostgreSQL.
"""
import logging
import sqlite3

logger = logging.getLogger(__name__)
pg_compatible = True


def _column_exists_sqlite(conn, table, column):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _resolve_default_ca_refid_sqlite(conn):
    """Return the configured SCEP CA refid (or None if nothing configured)."""
    try:
        row = conn.execute(
            "SELECT value FROM system_config WHERE key = 'scep_ca_id'"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row or not row[0]:
        return None
    raw = row[0]
    # Stored either as int (legacy) or refid string. Try refid first.
    cur = conn.execute(
        "SELECT refid FROM certificate_authorities WHERE refid = ?", (raw,)
    )
    found = cur.fetchone()
    if found:
        return found[0]
    try:
        cur = conn.execute(
            "SELECT refid FROM certificate_authorities WHERE id = ?", (int(raw),)
        )
        found = cur.fetchone()
        if found:
            return found[0]
    except (ValueError, TypeError):
        pass
    return None


def _upgrade_sqlite(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='scep_requests'"
    )
    if not cur.fetchone():
        logger.info("Migration 028: scep_requests table absent, skipping")
        return

    if _column_exists_sqlite(conn, 'scep_requests', 'ca_refid'):
        logger.info("Migration 028: ca_refid already present, skipping")
        return

    default_ca = _resolve_default_ca_refid_sqlite(conn)

    # Add nullable column first so existing rows aren't broken.
    conn.execute("ALTER TABLE scep_requests ADD COLUMN ca_refid VARCHAR(36)")

    if default_ca:
        conn.execute(
            "UPDATE scep_requests SET ca_refid = ? WHERE ca_refid IS NULL",
            (default_ca,),
        )
        logger.info(
            f"Migration 028: backfilled scep_requests.ca_refid={default_ca}"
        )
    else:
        logger.warning(
            "Migration 028: no scep_ca_id configured; existing scep_requests "
            "rows kept with NULL ca_refid (will collide with future inserts)"
        )

    # Recreate the table to drop the standalone UNIQUE on transaction_id
    # and replace it with a composite UNIQUE(transaction_id, ca_refid).
    # SQLite has no DROP CONSTRAINT, so we do the standard table-rebuild dance.
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("""
            CREATE TABLE scep_requests_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id VARCHAR(100) NOT NULL,
                ca_refid VARCHAR(36),
                csr TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                approved_by VARCHAR(80),
                approved_at DATETIME,
                rejection_reason VARCHAR(255),
                cert_refid VARCHAR(36),
                subject TEXT,
                client_ip VARCHAR(45),
                created_at DATETIME,
                UNIQUE(transaction_id, ca_refid)
            )
        """)
        conn.execute("""
            INSERT INTO scep_requests_new
                (id, transaction_id, ca_refid, csr, status, approved_by,
                 approved_at, rejection_reason, cert_refid, subject,
                 client_ip, created_at)
            SELECT id, transaction_id, ca_refid, csr, status, approved_by,
                   approved_at, rejection_reason, cert_refid, subject,
                   client_ip, created_at
            FROM scep_requests
        """)
        conn.execute("DROP TABLE scep_requests")
        conn.execute("ALTER TABLE scep_requests_new RENAME TO scep_requests")
        conn.execute(
            "CREATE INDEX ix_scep_requests_transaction_id "
            "ON scep_requests(transaction_id)"
        )
    finally:
        conn.execute("PRAGMA foreign_keys=ON")

    logger.info(
        "Migration 028: rebuilt scep_requests with UNIQUE(transaction_id, ca_refid)"
    )


def _upgrade_pg(conn):
    from sqlalchemy import text

    res = conn.execute(text(
        "SELECT to_regclass('public.scep_requests')"
    )).fetchone()
    if not res or not res[0]:
        logger.info("Migration 028: scep_requests table absent, skipping")
        return

    existing = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'scep_requests'"
    )).fetchall()
    cols = {row[0] for row in existing}
    if 'ca_refid' in cols:
        logger.info("Migration 028: ca_refid already present, skipping")
        return

    conn.execute(text(
        "ALTER TABLE scep_requests ADD COLUMN ca_refid VARCHAR(36)"
    ))

    row = conn.execute(text(
        "SELECT value FROM system_config WHERE key = 'scep_ca_id'"
    )).fetchone()
    default_ca = None
    if row and row[0]:
        raw = row[0]
        match = conn.execute(text(
            "SELECT refid FROM certificate_authorities WHERE refid = :r"
        ), {"r": raw}).fetchone()
        if match:
            default_ca = match[0]
        else:
            try:
                match = conn.execute(text(
                    "SELECT refid FROM certificate_authorities WHERE id = :i"
                ), {"i": int(raw)}).fetchone()
                if match:
                    default_ca = match[0]
            except (ValueError, TypeError):
                pass

    if default_ca:
        conn.execute(text(
            "UPDATE scep_requests SET ca_refid = :r WHERE ca_refid IS NULL"
        ), {"r": default_ca})
        logger.info(f"Migration 028: backfilled scep_requests.ca_refid={default_ca}")

    # Drop the old unique constraint (auto-named) on transaction_id, add composite.
    constraint_rows = conn.execute(text(
        "SELECT conname FROM pg_constraint c "
        "JOIN pg_class t ON t.oid = c.conrelid "
        "WHERE t.relname = 'scep_requests' AND c.contype = 'u'"
    )).fetchall()
    for (cname,) in constraint_rows:
        # Drop any unique constraint on transaction_id alone.
        cols_in = conn.execute(text(
            "SELECT a.attname FROM pg_constraint c "
            "JOIN pg_attribute a ON a.attrelid = c.conrelid "
            "  AND a.attnum = ANY(c.conkey) "
            "WHERE c.conname = :n"
        ), {"n": cname}).fetchall()
        names = [r[0] for r in cols_in]
        if names == ['transaction_id']:
            conn.execute(text(f'ALTER TABLE scep_requests DROP CONSTRAINT "{cname}"'))
            logger.info(f"Migration 028: dropped pg constraint {cname}")

    conn.execute(text(
        "ALTER TABLE scep_requests ADD CONSTRAINT scep_requests_txn_ca_uniq "
        "UNIQUE (transaction_id, ca_refid)"
    ))


def upgrade(conn):
    if isinstance(conn, sqlite3.Connection):
        _upgrade_sqlite(conn)
    else:
        _upgrade_pg(conn)


def downgrade(conn):
    """Irreversible — left as no-op."""
    pass
