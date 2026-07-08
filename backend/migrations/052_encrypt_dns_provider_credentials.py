"""Migration 052: encrypt DNS provider credentials at rest.

``dns_providers.credentials`` historically stored the provider API
keys/tokens (Cloudflare, Route53, ...) as plaintext JSON, despite the column
comment claiming otherwise (GHSA-38cv-3c4g-w55w). The model now encrypts the
field on write via a ``credentials`` property (utils.encryption Fernet).

This migration walks the existing rows once and rewrites any plaintext JSON to
the encrypted form so already-configured providers are protected at rest, not
just newly created ones.

Idempotent: ``encrypt_if_needed`` skips values already in Fernet form, and a
plaintext ``{"...": "..."}`` JSON never matches the Fernet prefix, so re-running
is safe. Encryption via utils.encryption always has a key (env / machine-id /
generated), so this is a no-op only when there are no rows.

Dual-backend (SQLite + PostgreSQL).
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)
pg_compatible = True


def _encrypt_if_needed():
    from utils.encryption import encrypt_if_needed
    return encrypt_if_needed


def _upgrade_sqlite(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='dns_providers'"
    )
    if not cur.fetchone():
        logger.info("052: dns_providers absent, skipping (fresh)")
        return

    try:
        encrypt_if_needed = _encrypt_if_needed()
    except Exception as e:  # pragma: no cover
        logger.warning(f"052: cannot import utils.encryption ({e}); skipping")
        return

    rows = conn.execute(
        "SELECT id, credentials FROM dns_providers WHERE credentials IS NOT NULL"
    ).fetchall()
    rewritten = 0
    for row in rows:
        pid, value = row[0], row[1]
        if not value:
            continue
        new_value = encrypt_if_needed(value)
        if new_value != value:
            conn.execute(
                "UPDATE dns_providers SET credentials = ? WHERE id = ?",
                (new_value, pid),
            )
            rewritten += 1
    conn.commit()
    if rewritten:
        logger.info(f"052: encrypted {rewritten} DNS provider credential(s) at rest (SQLite)")


def _upgrade_pg(conn):
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if 'dns_providers' not in set(insp.get_table_names()):
        logger.info("052: dns_providers absent, skipping (fresh PG)")
        return

    try:
        encrypt_if_needed = _encrypt_if_needed()
    except Exception as e:  # pragma: no cover
        logger.warning(f"052: cannot import utils.encryption ({e}); skipping")
        return

    rows = conn.execute(text(
        "SELECT id, credentials FROM dns_providers WHERE credentials IS NOT NULL"
    )).fetchall()
    rewritten = 0
    for row in rows:
        pid, value = row[0], row[1]
        if not value:
            continue
        new_value = encrypt_if_needed(value)
        if new_value != value:
            conn.execute(
                text("UPDATE dns_providers SET credentials = :v WHERE id = :i"),
                {"v": new_value, "i": pid},
            )
            rewritten += 1
    if rewritten:
        logger.info(f"052: encrypted {rewritten} DNS provider credential(s) at rest (PostgreSQL)")


def upgrade(conn):
    if isinstance(conn, sqlite3.Connection):
        _upgrade_sqlite(conn)
    else:
        _upgrade_pg(conn)


def downgrade(conn):
    """Best effort: decrypt back to plaintext JSON so old code can read them."""
    try:
        from utils.encryption import decrypt_if_needed
    except Exception:
        return

    if isinstance(conn, sqlite3.Connection):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dns_providers'"
        )
        if not cur.fetchone():
            return
        rows = conn.execute(
            "SELECT id, credentials FROM dns_providers WHERE credentials IS NOT NULL"
        ).fetchall()
        for row in rows:
            pid, value = row[0], row[1]
            if not value:
                continue
            plain = decrypt_if_needed(value)
            if plain != value:
                conn.execute(
                    "UPDATE dns_providers SET credentials = ? WHERE id = ?",
                    (plain, pid),
                )
        conn.commit()
    else:
        from sqlalchemy import text
        rows = conn.execute(text(
            "SELECT id, credentials FROM dns_providers WHERE credentials IS NOT NULL"
        )).fetchall()
        for row in rows:
            pid, value = row[0], row[1]
            if not value:
                continue
            plain = decrypt_if_needed(value)
            if plain != value:
                conn.execute(
                    text("UPDATE dns_providers SET credentials = :v WHERE id = :i"),
                    {"v": plain, "i": pid},
                )
