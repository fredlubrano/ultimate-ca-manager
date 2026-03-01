"""
Migration 040 — Certificate Discovery v2 tables

Creates:
  - discovery_scan_profiles: saved scan configurations with scheduling
  - discovery_scan_runs: scan execution history
  - discovered_certificates: certificates found via network scanning
"""


def upgrade(conn):
    # Drop v1 table if exists (clean slate for v2)
    conn.execute("DROP TABLE IF EXISTS discovered_certificates")
    conn.executescript("""
        -- Scan profiles: saved scan configurations with optional scheduling
        CREATE TABLE IF NOT EXISTS discovery_scan_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(200) NOT NULL UNIQUE,
            description TEXT,
            targets TEXT NOT NULL DEFAULT '[]',
            ports TEXT NOT NULL DEFAULT '[443]',
            schedule_enabled INTEGER NOT NULL DEFAULT 0,
            schedule_interval_minutes INTEGER NOT NULL DEFAULT 1440,
            notify_on_new INTEGER NOT NULL DEFAULT 1,
            notify_on_change INTEGER NOT NULL DEFAULT 1,
            notify_on_expiry INTEGER NOT NULL DEFAULT 1,
            last_scan_at DATETIME,
            next_scan_at DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Scan runs: execution history
        CREATE TABLE IF NOT EXISTS discovery_scan_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_profile_id INTEGER,
            started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            status VARCHAR(32) NOT NULL DEFAULT 'running',
            total_targets INTEGER NOT NULL DEFAULT 0,
            targets_scanned INTEGER NOT NULL DEFAULT 0,
            certs_found INTEGER NOT NULL DEFAULT 0,
            new_certs INTEGER NOT NULL DEFAULT 0,
            changed_certs INTEGER NOT NULL DEFAULT 0,
            errors INTEGER NOT NULL DEFAULT 0,
            triggered_by VARCHAR(32) NOT NULL DEFAULT 'manual',
            triggered_by_user VARCHAR(100),
            FOREIGN KEY (scan_profile_id) REFERENCES discovery_scan_profiles(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS ix_scan_runs_profile ON discovery_scan_runs(scan_profile_id);
        CREATE INDEX IF NOT EXISTS ix_scan_runs_status ON discovery_scan_runs(status);
        CREATE INDEX IF NOT EXISTS ix_scan_runs_started ON discovery_scan_runs(started_at);

        -- Discovered certificates: found via TLS scanning
        CREATE TABLE IF NOT EXISTS discovered_certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_profile_id INTEGER,
            target VARCHAR(1024) NOT NULL,
            port INTEGER NOT NULL DEFAULT 443,
            subject TEXT,
            issuer TEXT,
            serial_number VARCHAR(100),
            not_before DATETIME,
            not_after DATETIME,
            fingerprint_sha256 VARCHAR(64),
            pem_certificate TEXT,
            status VARCHAR(32) NOT NULL DEFAULT 'unmanaged',
            ucm_certificate_id INTEGER,
            first_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_changed_at DATETIME,
            previous_fingerprint VARCHAR(64),
            scan_error TEXT,
            FOREIGN KEY (scan_profile_id) REFERENCES discovery_scan_profiles(id) ON DELETE SET NULL,
            FOREIGN KEY (ucm_certificate_id) REFERENCES certificates(id) ON DELETE SET NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_disc_cert_target_port ON discovered_certificates(target, port);
        CREATE INDEX IF NOT EXISTS ix_disc_cert_fingerprint ON discovered_certificates(fingerprint_sha256);
        CREATE INDEX IF NOT EXISTS ix_disc_cert_status ON discovered_certificates(status);
        CREATE INDEX IF NOT EXISTS ix_disc_cert_not_after ON discovered_certificates(not_after);
        CREATE INDEX IF NOT EXISTS ix_disc_cert_profile ON discovered_certificates(scan_profile_id);
    """)
    conn.commit()


def downgrade(conn):
    conn.execute("DROP TABLE IF EXISTS discovered_certificates")
    conn.execute("DROP TABLE IF EXISTS discovery_scan_runs")
    conn.execute("DROP TABLE IF EXISTS discovery_scan_profiles")
    conn.commit()
