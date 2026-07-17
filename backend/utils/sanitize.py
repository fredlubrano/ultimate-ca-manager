"""Sanitization utilities for user-controlled input."""

import re


def sanitize_filename(name):
    """Sanitize a string for safe use in Content-Disposition headers.

    Removes/replaces characters that could cause header injection or
    filesystem issues.
    """
    if not name:
        return 'download'
    # Remove any control characters and CRLF
    name = re.sub(r'[\x00-\x1f\x7f\r\n]', '', name)
    # Remove path separators
    name = re.sub(r'[/\\]', '_', name)
    # Remove quotes
    name = name.replace('"', '')
    # Limit length
    name = name[:200]
    return name or 'download'


def ca_url_slug(name):
    """URL-safe slug from a CA name for named protocol URLs (#207)."""
    return re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-')[:48]


def crl_download_filename(ca, delta=False):
    """Readable CRL filename for Content-Disposition (#207).

    URLs keep the refid (they are embedded in issued certificates); only the
    suggested download name uses the CA description, e.g. ``lan-ca-6382320a.crl``.
    """
    slug = re.sub(r'[^a-z0-9]+', '-', (ca.descr or '').lower()).strip('-')[:40]
    ref = (ca.refid or '')[:8]
    base = f"{slug}-{ref}" if slug else (ref or 'ca')
    return f"{base}-delta.crl" if delta else f"{base}.crl"
