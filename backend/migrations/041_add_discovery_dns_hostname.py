"""
Migration 041 — Add dns_hostname to discovered_certificates
and scan_options (timeout, max_workers, resolve_dns) to scan profiles + runs.
"""


def upgrade(conn):
    # Add dns_hostname to discovered certificates
    try:
        conn.execute("ALTER TABLE discovered_certificates ADD COLUMN dns_hostname VARCHAR(1024)")
    except Exception:
        pass  # Column may already exist

    # Add scan options to profiles
    for col, default in [
        ("timeout", "5"),
        ("max_workers", "20"),
        ("resolve_dns", "0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE discovery_scan_profiles ADD COLUMN {col} INTEGER NOT NULL DEFAULT {default}")
        except Exception:
            pass

    # Add scan options to runs (record what was used)
    for col, default in [
        ("timeout", "5"),
        ("max_workers", "20"),
        ("resolve_dns", "0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE discovery_scan_runs ADD COLUMN {col} INTEGER NOT NULL DEFAULT {default}")
        except Exception:
            pass

    conn.commit()


def downgrade(conn):
    # SQLite doesn't support DROP COLUMN before 3.35
    pass
