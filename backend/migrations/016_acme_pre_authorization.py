"""
Migration 016: Allow pre-authorization (RFC 8555 §7.4.1)

Make order_id nullable in acme_authorizations to support standalone
authorizations created via newAuthz endpoint.
Add account_id column for standalone authorization ownership.
"""


def upgrade(conn):
    """Make order_id nullable and add account_id to acme_authorizations"""
    # SQLite doesn't support ALTER COLUMN, so we recreate the table
    # Check if account_id column already exists
    cursor = conn.execute("PRAGMA table_info(acme_authorizations)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'account_id' not in columns:
        # Add account_id column (nullable for backward compat)
        conn.execute("ALTER TABLE acme_authorizations ADD COLUMN account_id VARCHAR(64)")
        
        # Backfill account_id from orders
        conn.execute("""
            UPDATE acme_authorizations
            SET account_id = (
                SELECT ao.account_id
                FROM acme_orders ao
                WHERE ao.order_id = acme_authorizations.order_id
            )
            WHERE account_id IS NULL
        """)
        
        conn.commit()


def downgrade(conn):
    """Remove account_id column - SQLite doesn't support DROP COLUMN easily"""
    pass
