"""Add request_data column to approval_requests table for deferred cert issuance"""


def upgrade(conn):
    # Check if column already exists
    cursor = conn.execute("PRAGMA table_info(approval_requests)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'request_data' not in columns:
        conn.execute("ALTER TABLE approval_requests ADD COLUMN request_data TEXT")
        conn.commit()


def downgrade(conn):
    pass  # SQLite doesn't support DROP COLUMN easily
