"""RFC 8555 §7.4.2 alternate certificate chain selection (preferredChain)."""
from __future__ import annotations

import logging
import re
from typing import Callable, List, Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

_ALTERNATE_LINK_RE = re.compile(
    r'<([^>]+)>\s*;\s*rel="alternate"',
    re.IGNORECASE,
)


def collect_link_header_values(headers) -> List[str]:
    """Return all Link header field-values from a requests-style headers mapping."""
    if headers is None:
        return []
    if hasattr(headers, 'get_all'):
        values = headers.get_all('Link')
        if values:
            return list(values)
    if hasattr(headers, 'getlist'):
        values = headers.getlist('Link')
        if values:
            return list(values)
    value = headers.get('Link') if hasattr(headers, 'get') else None
    return [value] if value else []


def parse_link_rel_alternate(link_header: str | None) -> List[str]:
    """Extract certificate URLs advertised with rel=\"alternate\"."""
    if not link_header:
        return []
    urls: List[str] = []
    seen = set()
    for match in _ALTERNATE_LINK_RE.finditer(link_header):
        url = match.group(1).strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def split_pem_certificates(pem_data: str) -> List[str]:
    """Split a PEM blob into individual certificate blocks."""
    blocks: List[str] = []
    current: List[str] = []
    for line in pem_data.strip().splitlines():
        current.append(line)
        if line.strip() == '-----END CERTIFICATE-----':
            blocks.append('\n'.join(current) + '\n')
            current = []
    return blocks


def chain_root_common_name(pem_chain: str) -> Optional[str]:
    """Return the subject CN of the last certificate in a PEM chain."""
    blocks = split_pem_certificates(pem_chain)
    if not blocks:
        return None
    try:
        cert = x509.load_pem_x509_certificate(
            blocks[-1].encode(), default_backend()
        )
        attrs = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
        if attrs:
            return str(attrs[0].value)
    except Exception as exc:
        logger.warning('Could not parse chain root CN: %s', exc)
    return None


def select_acme_certificate_chain(
    default_pem: str,
    link_headers,
    preferred_root_cn: Optional[str],
    fetch_alternate: Callable[[str], str],
) -> str:
    """Pick an ACME certificate chain, optionally matching preferred_root_cn.

    Args:
        default_pem: PEM chain from the primary certificate URL response.
        link_headers: Response headers (or pre-joined Link string) with alternates.
        preferred_root_cn: Desired root subject CN (e.g. ``ISRG Root X1``), or None.
        fetch_alternate: Callable that POST-as-GETs an alternate cert URL and returns PEM.

    Returns:
        Selected PEM chain (default or an alternate).
    """
    preferred = (preferred_root_cn or '').strip()
    if not preferred:
        return default_pem

    preferred_lower = preferred.casefold()

    default_root = chain_root_common_name(default_pem)
    if default_root and default_root.casefold() == preferred_lower:
        return default_pem

    alternate_urls: List[str] = []
    if isinstance(link_headers, str):
        alternate_urls = parse_link_rel_alternate(link_headers)
    else:
        for header_value in collect_link_header_values(link_headers):
            alternate_urls.extend(parse_link_rel_alternate(header_value))
    # Preserve order while deduplicating.
    alternate_urls = list(dict.fromkeys(alternate_urls))

    for url in alternate_urls:
        try:
            alt_pem = fetch_alternate(url)
            if not alt_pem or not alt_pem.strip():
                continue
            root_cn = chain_root_common_name(alt_pem)
            if root_cn and root_cn.casefold() == preferred_lower:
                logger.info(
                    'Selected alternate ACME chain (root CN=%s) over default',
                    root_cn,
                )
                return alt_pem
        except Exception as exc:
            logger.warning('Failed to fetch alternate ACME chain from %s: %s', url, exc)

    logger.warning(
        'preferred_chain %r did not match any alternate (default root=%r); '
        'keeping default chain',
        preferred,
        default_root,
    )
    return default_pem
