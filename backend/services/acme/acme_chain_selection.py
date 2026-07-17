"""RFC 8555 §7.4.2 alternate certificate chain selection (preferredChain)."""
from __future__ import annotations

import logging
import re
from typing import Callable, List, Optional, Tuple

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


def _load_cert(block: str) -> x509.Certificate:
    return x509.load_pem_x509_certificate(block.encode(), default_backend())


def _cert_serial(block: str) -> int:
    return _load_cert(block).serial_number


def _cert_common_name(name: x509.Name) -> Optional[str]:
    attrs = name.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
    if attrs:
        return str(attrs[0].value)
    return None


def chain_root_common_name(pem_chain: str) -> Optional[str]:
    """Return the subject CN of the last certificate in a PEM chain."""
    blocks = split_pem_certificates(pem_chain)
    if not blocks:
        return None
    try:
        return _cert_common_name(_load_cert(blocks[-1]).subject)
    except Exception as exc:
        logger.warning('Could not parse chain root CN: %s', exc)
    return None


def chain_matches_preferred_cn(pem_chain: str, preferred_cn: str) -> bool:
    """True when the last cert's subject or issuer CN matches *preferred_cn*.

    RFC 8555 chains often omit the self-signed root; certbot/acme.sh match the
    issuer CN of the topmost certificate in that case.
    """
    blocks = split_pem_certificates(pem_chain)
    if not blocks:
        return False
    preferred_lower = preferred_cn.casefold()
    try:
        last = _load_cert(blocks[-1])
        for name in (last.subject, last.issuer):
            cn = _cert_common_name(name)
            if cn and cn.casefold() == preferred_lower:
                return True
    except Exception as exc:
        logger.warning('Could not evaluate preferred chain match: %s', exc)
    return False


def chain_issuer_serials(pem_chain: str) -> Tuple[int, ...]:
    """Serial numbers of issuer certificates (all certs after the leaf)."""
    blocks = split_pem_certificates(pem_chain)
    if len(blocks) <= 1:
        return ()
    serials: List[int] = []
    for block in blocks[1:]:
        try:
            serials.append(_cert_serial(block))
        except Exception as exc:
            logger.warning('Could not parse issuer serial in chain: %s', exc)
    return tuple(serials)


def _leaf_subject_cn(block: str) -> Optional[str]:
    try:
        attrs = _load_cert(block).subject.get_attributes_for_oid(
            x509.oid.NameOID.COMMON_NAME
        )
        if attrs:
            return str(attrs[0].value)
    except Exception:
        pass
    return None


def rebuild_acme_chain(primary_pem: str, chain_pem: str) -> str:
    """Build a full chain using the leaf from *primary_pem* and issuers from *chain_pem*.

    Some CAs return alternates as issuer-only PEM (no leaf). Others return a full
    chain; when the first certificate is the same leaf (serial or subject CN),
    issuer certs are taken from the remainder of the alternate response.
    """
    primary_blocks = split_pem_certificates(primary_pem)
    chain_blocks = split_pem_certificates(chain_pem)
    if not primary_blocks:
        return chain_pem
    if not chain_blocks:
        return primary_pem

    leaf = primary_blocks[0]
    try:
        leaf_serial = _cert_serial(leaf)
        leaf_cn = _leaf_subject_cn(leaf)
        first = chain_blocks[0]
        same_leaf = (
            _cert_serial(first) == leaf_serial
            or (
                len(chain_blocks) > 1
                and leaf_cn
                and _leaf_subject_cn(first) == leaf_cn
            )
        )
        issuer_blocks = chain_blocks[1:] if same_leaf else chain_blocks
    except Exception as exc:
        logger.warning('Chain rebuild serial compare failed: %s', exc)
        return chain_pem if chain_blocks else primary_pem

    if not issuer_blocks and len(primary_blocks) > 1:
        issuer_blocks = primary_blocks[1:]

    return ''.join([leaf, *issuer_blocks])


def _collect_alternate_urls(link_headers) -> List[str]:
    alternate_urls: List[str] = []
    if isinstance(link_headers, str):
        alternate_urls = parse_link_rel_alternate(link_headers)
    else:
        for header_value in collect_link_header_values(link_headers):
            alternate_urls.extend(parse_link_rel_alternate(header_value))
    return list(dict.fromkeys(alternate_urls))


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
        preferred_root_cn: Desired trust-anchor CN (e.g. ``ISRG Root X1``). Matches
            the last certificate's subject CN or issuer CN when the root is omitted.
        fetch_alternate: Callable that POST-as-GETs an alternate cert URL and returns PEM.

    Returns:
        Selected PEM chain (default or an alternate, rebuilt with the primary leaf).
    """
    preferred = (preferred_root_cn or '').strip()
    if not preferred:
        return default_pem

    preferred_lower = preferred.casefold()
    alternate_urls = _collect_alternate_urls(link_headers)
    default_root = chain_root_common_name(default_pem)
    default_issuers = chain_issuer_serials(default_pem)

    if chain_matches_preferred_cn(default_pem, preferred_lower) and not alternate_urls:
        return default_pem

    best_pem: Optional[str] = None
    best_issuers: Optional[Tuple[int, ...]] = None
    best_is_alternate = False

    def _consider_candidate(pem: str, is_alternate: bool) -> None:
        nonlocal best_pem, best_issuers, best_is_alternate
        if not chain_matches_preferred_cn(pem, preferred_lower):
            return
        rebuilt = rebuild_acme_chain(default_pem, pem)
        issuers = chain_issuer_serials(rebuilt)
        if best_pem is None:
            best_pem, best_issuers, best_is_alternate = rebuilt, issuers, is_alternate
            return
        # Default already matches — keep it unless an alternate offers different issuers.
        if not best_is_alternate:
            if is_alternate and issuers != best_issuers:
                best_pem, best_issuers, best_is_alternate = rebuilt, issuers, True
            return
        # First matching alternate wins (certbot-style).
    _consider_candidate(default_pem, is_alternate=False)

    for url in alternate_urls:
        try:
            alt_pem = fetch_alternate(url)
            if alt_pem and alt_pem.strip():
                _consider_candidate(alt_pem, is_alternate=True)
        except Exception as exc:
            logger.warning('Failed to fetch alternate ACME chain from %s: %s', url, exc)

    if best_pem is not None:
        if best_is_alternate:
            logger.info(
                'Selected alternate ACME chain (root CN=%s, issuers=%s)',
                chain_root_common_name(best_pem),
                best_issuers,
            )
        return best_pem

    logger.warning(
        'preferred_chain %r did not match any alternate (default root=%r); '
        'keeping default chain',
        preferred,
        default_root,
    )
    return default_pem
