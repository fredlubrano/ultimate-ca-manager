"""
Migration 010: Add key_type column to acme_client_orders
Supports ECDSA and RSA key type selection for ACME certificate requests.
"""

def upgrade(conn):
    # Check if column already exists
    cursor = conn.execute("PRAGMA table_info(acme_client_orders)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'key_type' not in columns:
        conn.execute(
            "ALTER TABLE acme_client_orders ADD COLUMN key_type VARCHAR(20) DEFAULT 'RSA-2048'"
        )
        conn.commit()


def downgrade(conn):
    pass  # SQLite cannot drop columns
