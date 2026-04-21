"""
Migration 020: Fix AcmeClientOrder.expires_at for issued orders (issue #74)

Background
----------
RFC 8555 §7.1.3 says the ACME order resource's ``expires`` field is the
expiry of the *order resource itself*, NOT the issued certificate's
``notAfter``. Let's Encrypt sets this to ~7 days.

Prior to v2.127, ``acme_client_service.finalize_order`` left
``order.expires_at`` at that 7-day value even after the certificate was
issued. ``acme_renewal_service.scheduled_acme_renewal`` then compares
``expires_at <= now + 30 days`` and concludes the cert needs renewal —
forever. This causes a renewal storm and trips the LE production rate
limits (`see issue #74 <https://github.com/NeySlim/ultimate-ca-manager/issues/74>`_).

This migration backfills ``expires_at`` on every issued order to the
linked certificate's actual ``not_after`` so the renewal scheduler stops
re-issuing them.
"""


def upgrade(conn):
    """Backfill expires_at from certificates.not_after for issued orders."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name IN ('acme_client_orders', 'certificates')"
    )
    tables = {row[0] for row in cursor.fetchall()}
    if 'acme_client_orders' not in tables or 'certificates' not in tables:
        return

    conn.execute("""
        UPDATE acme_client_orders
        SET expires_at = (
            SELECT certificates.not_after
            FROM certificates
            WHERE certificates.id = acme_client_orders.certificate_id
        )
        WHERE acme_client_orders.status = 'issued'
          AND acme_client_orders.certificate_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM certificates
              WHERE certificates.id = acme_client_orders.certificate_id
                AND certificates.not_after IS NOT NULL
          )
    """)
    conn.commit()


def downgrade(conn):
    """No-op — we won't restore the broken 7-day window."""
    pass
