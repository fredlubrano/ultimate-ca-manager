"""Shared upstream HTTP stubs for ACME proxy protocol tests.

After SSRF hardening, AcmeProxyService uses utils.ssrf_protection.safe_request_*
instead of bare requests.* — tests must patch the pinned helpers.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def stub_acme_proxy_upstream(
    monkeypatch,
    fake_directory: Optional[Dict[str, Any]] = None,
    post_handler: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Patch safe_request_get/head/post for AcmeProxyService upstream calls."""
    if fake_directory is None:
        fake_directory = {
            'newNonce': 'https://acme-stub.example/acme/new-nonce',
            'newAccount': 'https://acme-stub.example/acme/new-account',
            'newOrder': 'https://acme-stub.example/acme/new-order',
            'meta': {},
        }

    class _FakeGetResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return fake_directory

    class _FakeHeadResp:
        headers = {'Replay-Nonce': 'upstream-stub-nonce'}

    class _FakePostResp:
        status_code = 201
        headers = {
            'Location': 'https://acme-stub.example/acme/acct/1',
            'Replay-Nonce': 'upstream-stub-nonce-2',
        }

        def json(self):
            return {'status': 'valid'}

    def _fake_get(*_args, **_kwargs):
        return _FakeGetResp()

    def _fake_head(*_args, **_kwargs):
        return _FakeHeadResp()

    def _fake_post(*args, **kwargs):
        if post_handler is not None:
            return post_handler(*args, **kwargs)
        return _FakePostResp()

    monkeypatch.setattr('utils.ssrf_protection.safe_request_get', _fake_get)
    monkeypatch.setattr('utils.ssrf_protection.safe_request_head', _fake_head)
    monkeypatch.setattr('utils.ssrf_protection.safe_request_post', _fake_post)
    return fake_directory
