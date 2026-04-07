"""
Migration 014: Multi-URL CDP/OCSP/AIA + CPS (Certificate Practice Statement)

Changes:
1. Convert cdp_url, ocsp_url, aia_ca_issuers_url from plain string to JSON array
   - "http://example.com/crl" → '["http://example.com/crl"]'
2. Add CPS (Certificate Practice Statement) columns:
   - cps_enabled: Enable Certificate Policies extension
   - cps_uri: CPS URI (e.g., http://ca.example.com/cps.pdf)
   - cps_oid: Policy OID (default: 2.5.29.32.0 = anyPolicy)

RFC References:
- RFC 5280 §4.2.1.13: CRL Distribution Points (multiple DPs)
- RFC 5280 §4.2.2.1: Authority Information Access (multiple access descriptions)
- RFC 5280 §4.2.1.4: Certificate Policies with CPS qualifier
"""

import json
import logging

logger = logging.getLogger(__name__)


def upgrade(conn):
    # 1. Convert existing URL columns to JSON arrays
    for col in ('cdp_url', 'ocsp_url', 'aia_ca_issuers_url'):
        cursor = conn.execute(f"SELECT id, {col} FROM certificate_authorities WHERE {col} IS NOT NULL AND {col} != ''")
        rows = cursor.fetchall()
        for row in rows:
            ca_id, url_value = row[0], row[1]
            # Skip if already a JSON array
            if url_value.startswith('['):
                continue
            json_array = json.dumps([url_value])
            conn.execute(f"UPDATE certificate_authorities SET {col} = ? WHERE id = ?", (json_array, ca_id))
        if rows:
            logger.info(f"Converted {len(rows)} CA {col} values to JSON arrays")

    # 2. Add CPS columns
    try:
        conn.execute("ALTER TABLE certificate_authorities ADD COLUMN cps_enabled BOOLEAN DEFAULT 0")
    except Exception:
        pass  # Column may already exist
    try:
        conn.execute("ALTER TABLE certificate_authorities ADD COLUMN cps_uri TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE certificate_authorities ADD COLUMN cps_oid TEXT DEFAULT '2.5.29.32.0'")
    except Exception:
        pass

    conn.commit()
    logger.info("Migration 014 applied: multi-URL + CPS support")


def downgrade(conn):
    # Convert JSON arrays back to plain strings (take first URL)
    for col in ('cdp_url', 'ocsp_url', 'aia_ca_issuers_url'):
        cursor = conn.execute(f"SELECT id, {col} FROM certificate_authorities WHERE {col} IS NOT NULL AND {col} != ''")
        rows = cursor.fetchall()
        for row in rows:
            ca_id, url_value = row[0], row[1]
            if url_value.startswith('['):
                try:
                    urls = json.loads(url_value)
                    if isinstance(urls, list) and urls:
                        conn.execute(f"UPDATE certificate_authorities SET {col} = ? WHERE id = ?", (urls[0], ca_id))
                except (json.JSONDecodeError, TypeError):
                    pass

    # Note: SQLite cannot DROP COLUMN in older versions, so CPS columns remain but are unused
    conn.commit()
    logger.info("Migration 014 downgraded: reverted to single URLs")
