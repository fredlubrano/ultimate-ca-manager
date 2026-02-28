"""Migration 040 - Create discovered_certificates table for network certificate discovery."""


def upgrade(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS discovered_certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target VARCHAR(1024) NOT NULL,
            port INTEGER NOT NULL DEFAULT 443,
            subject TEXT,
            issuer TEXT,
            serial_number VARCHAR(100),
            not_before DATETIME,
            not_after DATETIME,
            fingerprint_sha256 VARCHAR(64),
            pem_certificate TEXT NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'unknown',
            ucm_certificate_id INTEGER,
            first_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            scan_error TEXT,
            FOREIGN KEY (ucm_certificate_id) REFERENCES certificates(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS ix_disc_cert_fingerprint ON discovered_certificates(fingerprint_sha256);
        CREATE INDEX IF NOT EXISTS ix_disc_cert_target ON discovered_certificates(target, port);
        CREATE INDEX IF NOT EXISTS ix_disc_cert_status ON discovered_certificates(status);
        CREATE INDEX IF NOT EXISTS ix_disc_cert_not_after ON discovered_certificates(not_after);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_disc_cert_target_port ON discovered_certificates(target, port);
    """)
    conn.commit()


def downgrade(conn):
    conn.execute("DROP TABLE IF EXISTS discovered_certificates")
    conn.commit()
