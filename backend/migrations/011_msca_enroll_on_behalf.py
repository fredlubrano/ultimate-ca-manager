"""Add Enroll on Behalf Of (EOBO) fields to msca_requests

Adds enrollee_name and enrollee_upn columns to track
ADCS enrollment agent operations (RFC 4556 / MS-WCCE).
"""


def upgrade(conn):
    cursor = conn.execute("PRAGMA table_info(msca_requests)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'enrollee_name' not in columns:
        conn.execute("ALTER TABLE msca_requests ADD COLUMN enrollee_name VARCHAR(500)")

    if 'enrollee_upn' not in columns:
        conn.execute("ALTER TABLE msca_requests ADD COLUMN enrollee_upn VARCHAR(500)")

    conn.commit()


def downgrade(conn):
    pass  # SQLite doesn't support DROP COLUMN in older versions
