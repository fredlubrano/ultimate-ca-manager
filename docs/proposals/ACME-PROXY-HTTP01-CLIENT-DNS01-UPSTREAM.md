# Proposal — ACME proxy: HTTP-01 client + DNS-01 upstream

> Status: **Draft / roadmap** (no code yet). This document describes a possible
> evolution of the ACME proxy. It is a design note, not an implemented feature.

## Context

Today the ACME proxy (`/acme/proxy/...`) is a **dns-01-only** gateway toward an
external CA (Let's Encrypt, Actalis, ZeroSSL…). External clients (Certbot,
win-acme…) must use `dns-01`; UCM automates the upstream `dns-01` TXT record via
a configured DNS provider.

Enforced in `backend/services/acme/acme_proxy_service.py`:

- `get_authz()` filters upstream challenges to `dns-01` only
- `respond_challenge()` rejects any challenge type other than `dns-01`
- `new_order()` hardcodes `challenge_type='dns-01'`

## Goal

Allow the **client** to validate with **HTTP-01** while UCM keeps satisfying the
**upstream** CA with **DNS-01**.

This is **not** an RFC 8555 challenge translation. It is a **dual, independent
validation** orchestrated by the proxy:

- the client proves domain control over **HTTP** using its **own** account key
- UCM proves domain control over **DNS** to the real CA using the **upstream**
  account key

The two proofs use different tokens and different JWK thumbprints — by design.

## Flow (target)

```
Client (Certbot)          Proxy UCM                    Real CA (Actalis…)
     │                         │                              │
     │  sees http-01           │  sees dns-01 upstream        │
     │  key = CLIENT account   │  key = UPSTREAM UCM account  │
     │                         │                              │
     │── GET authz ───────────►│── GET upstream authz ───────►│
     │◄─ http-01 challenge ────│◄─ dns-01 challenge ──────────│
     │                         │                              │
     │  publishes token+thumb  │                              │
     │  on the domain (HTTP)   │                              │
     │── POST challenge ──────►│  validates HTTP-01 (client)  │
     │                         │── creates TXT + POST ───────►│
     │                         │                              │
     │── POST finalize ───────►│── POST finalize upstream ───►│
     │◄─ certificate ──────────│◄─ certificate ───────────────│
```

The client never sees the upstream `dns-01`. UCM triggers it in the background
**only after** the client's HTTP-01 validation succeeds.

## Required changes

### 1. Configuration and data model

| File | Change |
|------|--------|
| `SystemConfig` / `AcmeClientAccount` | New setting `proxy_client_challenge_type`: `dns-01` (default) or `http-01` |
| `AcmeClientOrder` | Split `client_challenge_type` and `upstream_challenge_type`; extend `challenges_dict` with a client↔upstream mapping |
| Migration | Add columns + config key `acme.proxy.client_challenge_type` |
| `api/v2/acme_client/proxy.py` | Expose the setting in API + UI |
| Frontend (ACME Settings) | Client challenge selector (HTTP-01 / DNS-01) + helper text |

### 2. `acme_proxy_service.py` — `new_order()`

- Read `proxy_client_challenge_type`
- Store `client_challenge_type='http-01'` and `upstream_challenge_type='dns-01'`
- Keep the DNS-provider requirement (needed for the upstream side)
- Persist the **client JWK thumbprint** (`client_jwk_thumbprint`, already present)

### 3. `get_authz()` — expose http-01 to the client

- In `http-01` mode, do **not** filter to `dns-01`
- Keep a reference to the upstream `dns-01` challenge URL + token
- Build a **synthetic** `http-01` challenge for the client (own token)
- Store in `challenges_dict`: client token, client thumbprint, upstream dns-01
  URL, upstream token
- Do **not** trigger `_bg_respond_challenge` at authz fetch — wait for the
  client HTTP validation

### 4. New client HTTP-01 validation on the proxy

Inspired by `backend/services/acme/mixins/challenge.py:validate_http01_challenge`.

```
key_authz = f"{client_token}.{client_jwk_thumbprint}"
GET http://<domain>/.well-known/acme-challenge/<client_token>
assert response.text.strip() == key_authz
```

Two possible hosting modes for the client HTTP-01 file:

| Mode | Who serves `/.well-known/` | Change |
|------|----------------------------|--------|
| **A — Client** | Certbot webroot/standalone on the domain | Proxy validates by fetching the URL |
| **B — UCM** | UCM on the public vhost (`acme_public_vhost`, v2.187) | Add route `GET /.well-known/acme-challenge/<token>` serving `key_authz`; domain must point at UCM |

### 5. `respond_challenge()` — chain HTTP then DNS

```
1. Client POST /challenge/{id}
2. Identify the client challenge (synthetic token)
3. validate_client_http01()  → on failure: return invalid
4. On success: launch _bg_respond_challenge() for the UPSTREAM dns-01
   (upstream challenge URL + UPSTREAM thumbprint)
5. Return status=processing to the client
6. Poll upstream; when dns-01 becomes valid → return valid to the client
```

### 6. `_bg_respond_challenge()` — adjustments

- Replace the fixed `time.sleep(30)` with the existing DNS self-check
  (`backend/utils/dns_txt_lookup.py` / `_dns_selfcheck`)
- Trigger only **after** the client HTTP-01 validation succeeds
- If HTTP fails, do not create the upstream TXT record

### 7. `acme_proxy_api.py` — routes and errors

| Change | Detail |
|--------|--------|
| `POST /challenge/{id}` | Branch http-01 vs dns-01 by config |
| RFC 8555 errors | `unsupportedChallenge`, `connection` if HTTP unreachable |
| `GET /.well-known/acme-challenge/<token>` | Only if UCM hosts the challenge (mode B) |
| Directory `meta` | Optionally advertise `http-01` as a proxy-supported challenge |

### 8. Security

| Risk | Mitigation |
|------|------------|
| SSRF on HTTP validation | Reuse `utils/ssrf_protection.validate_host_not_private` |
| Token replay | TTL + delete after use |
| Client/upstream race | Per-`order_id` lock during validation |
| Wildcard `*.domain` | HTTP-01 forbidden on wildcards (RFC 8555 §8.4) → reject or force dns-01 |
| Duplicate requests | Keep the current "TXT overwritten" warning |

### 9. UI, i18n, documentation

| File | Change |
|------|--------|
| `frontend/src/i18n/locales/*.json` | Update `proxyUsageNote`: http-01 client mode |
| ACME Settings | Client challenge selector + Certbot `--preferred-challenges http` hint |
| `docs/testing/ACME-PROXY-MULTI-CA.md` | Add Certbot http-01 + upstream dns-01 scenario |
| `CHANGELOG.md` | New feature entry |

### 10. Tests

| File | Content |
|------|---------|
| `backend/tests/test_acme_proxy_http_client.py` | authz exposes http-01; POST challenge triggers upstream DNS |
| | HTTP validation OK/KO |
| | Client vs upstream thumbprints are distinct |
| | Wildcard rejected in http-01 mode |
| | Regression: dns-01 mode unchanged |

## Estimated effort

| Phase | Effort | Content |
|-------|--------|---------|
| 1 | ~2–3 d | Config + synthetic `get_authz` + `respond_challenge` HTTP branch |
| 2 | ~1–2 d | `validate_client_http01` + `_bg_respond_challenge` chaining |
| 3 | ~1 d | DNS self-check (replace 30s sleep) + error handling |
| 4 | ~1 d | UI + i18n + docs |
| 5 | ~1–2 d | E2E tests (Certbot `--preferred-challenges http`) |

**Total:** ~6–9 days of dev + tests.

## Open questions

- Mode A (client-hosted) vs Mode B (UCM-hosted) — support one or both?
- Should the proxy advertise `http-01` in the directory `meta`, or keep it
  implicit per-account?
- Behaviour when the upstream CA does not offer `dns-01` (should already fail
  today) — surface a clear error in http-01 mode too.

## Key takeaway

This is a **dual-validation proxy**, not an RFC challenge conversion. The client
and UCM each prove domain control independently (HTTP for the client, DNS for
UCM upstream), and the proxy links the two halves.
