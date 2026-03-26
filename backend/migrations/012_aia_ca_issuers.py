"""
Migration 012: Add AIA CA Issuers fields to certificate_authorities

Adds aia_ca_issuers_enabled and aia_ca_issuers_url fields for
Authority Information Access - CA Issuers extension (RFC 5280 §4.2.2.1).
"""

def upgrade(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(certificate_authorities)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'aia_ca_issuers_enabled' not in columns:
        conn.execute("ALTER TABLE certificate_authorities ADD COLUMN aia_ca_issuers_enabled BOOLEAN DEFAULT 0")
    if 'aia_ca_issuers_url' not in columns:
        conn.execute("ALTER TABLE certificate_authorities ADD COLUMN aia_ca_issuers_url VARCHAR(512)")
    
    conn.commit()


def downgrade(conn):
    pass  # SQLite doesn't support DROP COLUMN cleanly
