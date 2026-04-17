"""
Migration 019: Make ACME auto_approve opt-in (issue #69)

Historically, `auto_approve` on `acme_domains` and `acme_local_domains` had
`default=TRUE` but was never read by the ACME service — it was purely
cosmetic. Starting with this migration, `auto_approve=TRUE` makes UCM skip
challenge validation entirely for matching identifiers (authorizations are
created directly in `valid` state, orders go straight to `ready`).

Because existing installs may have left the toggle on `TRUE` without knowing
it was inert, flipping this flag to "skip challenges" globally would silently
weaken security. This migration resets `auto_approve` to FALSE on every
existing row so administrators must explicitly re-enable the feature per
domain after reviewing the new behavior.

The column default on the model is also switched to FALSE (see
models/acme_models.py) so new entries created via the UI/API after upgrade
start opted out unless the admin checks the box.

See issue: https://github.com/NeySlim/ultimate-ca-manager/issues/69
"""


def upgrade(conn):
    """Reset auto_approve to FALSE on all existing ACME domain rows."""
    cursor = conn.execute("PRAGMA table_info(acme_domains)")
    if any(row[1] == 'auto_approve' for row in cursor.fetchall()):
        conn.execute("UPDATE acme_domains SET auto_approve = 0 WHERE auto_approve = 1")

    cursor = conn.execute("PRAGMA table_info(acme_local_domains)")
    if any(row[1] == 'auto_approve' for row in cursor.fetchall()):
        conn.execute("UPDATE acme_local_domains SET auto_approve = 0 WHERE auto_approve = 1")

    conn.commit()


def downgrade(conn):
    """No-op — we won't blindly re-enable auto_approve on rollback."""
    pass
