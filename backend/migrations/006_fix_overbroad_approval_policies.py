"""
Migration 006: Fix overbroad approval policies

The seed data "Code Signing" policy has requires_approval=True but no
narrowing rules (no dns_pattern, no template, no CA scope), so it matches
ALL certificate requests. Deactivate it so users can configure it properly.
"""

def upgrade(conn):
    # Deactivate "Code Signing" policy that has no narrowing rules
    conn.execute(
        "UPDATE certificate_policies SET is_active = 0 "
        "WHERE name = 'Code Signing' AND requires_approval = 1 "
        "AND ca_id IS NULL AND template_id IS NULL"
    )
    conn.commit()


def downgrade(conn):
    conn.execute(
        "UPDATE certificate_policies SET is_active = 1 "
        "WHERE name = 'Code Signing'"
    )
    conn.commit()
