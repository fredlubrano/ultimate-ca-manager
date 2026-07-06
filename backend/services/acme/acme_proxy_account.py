"""Resolve the external ACME CA account used as the proxy upstream.

The proxy reuses ``AcmeClientAccount`` rows (same registry as the ACME client)
instead of maintaining a parallel set of SystemConfig credentials.
"""
from __future__ import annotations

import logging
from typing import Optional

from models import SystemConfig
from models.acme_client_account import AcmeClientAccount

logger = logging.getLogger(__name__)

PROXY_ACCOUNT_ID_KEY = 'acme.proxy.acme_account_id'

MODE_URLS = {
    'production': AcmeClientAccount.LE_PRODUCTION_URL,
    'staging': AcmeClientAccount.LE_STAGING_URL,
}


def _get_config(key: str) -> Optional[str]:
    row = SystemConfig.query.filter_by(key=key).first()
    if not row or row.value is None:
        return None
    val = str(row.value).strip()
    return val or None


def _legacy_upstream_directory_url() -> str:
    """Derive upstream directory URL from legacy proxy SystemConfig keys."""
    custom = _get_config('acme.proxy.upstream_url')
    if custom:
        return custom
    mode = _get_config('acme.proxy.upstream_mode') or 'staging'
    return MODE_URLS.get(mode, AcmeClientAccount.LE_STAGING_URL)


def resolve_proxy_account(explicit_id: Optional[int] = None) -> AcmeClientAccount:
    """Return the ``AcmeClientAccount`` row the proxy should use upstream.

    Priority:
      1. ``explicit_id`` argument (API override)
      2. ``acme.proxy.acme_account_id`` SystemConfig
      3. Account matching legacy ``acme.proxy.upstream_url`` / mode
      4. Row marked ``is_default=True``
      5. Let's Encrypt staging (creates a placeholder if missing)
    """
    account_id = explicit_id
    if account_id is None:
        raw = _get_config(PROXY_ACCOUNT_ID_KEY)
        if raw:
            try:
                account_id = int(raw)
            except ValueError:
                logger.warning("Invalid %s value: %r", PROXY_ACCOUNT_ID_KEY, raw)

    if account_id is not None:
        acct = AcmeClientAccount.query.get(account_id)
        if not acct:
            raise RuntimeError(f"Configured proxy CA account id={account_id} was not found")
        return acct

    legacy_url = _legacy_upstream_directory_url()
    acct = AcmeClientAccount.query.filter_by(directory_url=legacy_url).first()
    if acct:
        return acct

    default = AcmeClientAccount.query.filter_by(is_default=True).first()
    if default:
        return default

    acct = AcmeClientAccount.query.filter_by(
        directory_url=AcmeClientAccount.LE_STAGING_URL
    ).first()
    if acct:
        return acct

    raise RuntimeError(
        "No external ACME CA account configured for the proxy. "
        "Add a CA account under ACME → External CA Accounts and select it for the proxy."
    )
