MIGRATION_SQL = """
ALTER TABLE certificate_authorities
  ADD COLUMN offline BOOLEAN DEFAULT 0;
ALTER TABLE certificate_authorities
  ADD COLUMN offline_reason TEXT;
ALTER TABLE certificate_authorities
  ADD COLUMN offline_mode TEXT;
"""

def upgrade(conn):
    conn.executescript(MIGRATION_SQL)
    conn.commit()

def downgrade(conn):
    conn.execute("ALTER TABLE certificate_authorities DROP COLUMN offline")
    conn.execute("ALTER TABLE certificate_authorities DROP COLUMN offline_reason")
    conn.execute("ALTER TABLE certificate_authorities DROP COLUMN offline_mode")
    conn.commit()
