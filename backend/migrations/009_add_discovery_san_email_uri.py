"""Add san_emails and san_uris columns to discovered_certificates table.

RFC 5280 compliance: store all SAN types (email/URI) from discovered certificates.
"""


def upgrade(conn):
    cursor = conn.cursor()
    # Check existing columns
    cursor.execute("PRAGMA table_info(discovered_certificates)")
    columns = {row[1] for row in cursor.fetchall()}

    if 'san_emails' not in columns:
        cursor.execute("ALTER TABLE discovered_certificates ADD COLUMN san_emails TEXT NOT NULL DEFAULT '[]'")
    if 'san_uris' not in columns:
        cursor.execute("ALTER TABLE discovered_certificates ADD COLUMN san_uris TEXT NOT NULL DEFAULT '[]'")

    conn.commit()


def downgrade(conn):
    pass  # SQLite doesn't support DROP COLUMN easily
