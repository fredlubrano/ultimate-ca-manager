# Proposal — ACME proxy: HTTP-01 client + DNS-01 upstream

> Status: **Draft / roadmap** (no code yet). This document describes a possible
> evolution of the ACME proxy. It is a design note, not an implemented feature.
>
> One part is carved out as an **independently shippable quick win** (phase 0):
> replacing the fixed DNS propagation sleep with an active self-check. See
> [Independent quick win — active DNS self-check](#independent-quick-win--active-dns-self-check).
> It requires no protocol change and can land before any HTTP-01 work.

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

- Replace the fixed `time.sleep(30)` with the active DNS self-check described in
  [Independent quick win — active DNS self-check](#independent-quick-win--active-dns-self-check)
- Trigger only **after** the client HTTP-01 validation succeeds
- If HTTP fails, do not create the upstream TXT record

> The self-check itself is **not** coupled to HTTP-01. It can (and should) ship
> first as a standalone change — see the dedicated section below.

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

## Independent quick win — active DNS self-check

This part is **decoupled** from HTTP-01 and can ship on its own. It only
changes *how long, and how, UCM waits before telling the upstream CA to
validate*. The client-facing protocol is unchanged.

### Problem

Both server-side automation paths currently wait for DNS propagation with a
**fixed blind sleep**, then submit to the CA regardless of whether the TXT
record is actually visible:

- `backend/services/acme/acme_proxy_service.py` → `_bg_respond_challenge()`:
  `time.sleep(30)`
- `backend/services/acme_renewal_service.py` → `time.sleep(30)` before
  submitting challenges

Consequences:

- **Too short** for slow authoritative zones / slow CAs → intermittent
  `unauthorized` (already documented for Actalis in
  `docs/testing/ACME-PROXY-MULTI-CA.md`, propagation ~30 s at the edge)
- **Too long** for fast providers → every issuance pays a flat 30 s tax
- On timeout the upstream challenge is submitted **anyway**, and the created
  TXT record is not cleaned up on the failure path

### Existing building block (client side, already shipped in v2.182)

The ACME **client** already solved this in `backend/api/v2/acme_client/orders.py`:

- `_dns_propagation_timeout()` reads `acme.client.dns_propagation_timeout`
  (0–3600 s, `0` = "submit immediately")
- `_dns_selfcheck(challenges, timeout)` polls every `_DNS_SELFCHECK_INTERVAL`
  (5 s) until every expected TXT is visible, using
  `utils/dns_txt_lookup.txt_record_present()`:
  configured resolvers → authoritative NS → `9.9.9.9 / 8.8.8.8 / 1.1.1.1` →
  system resolver, with per-resolver diagnostic logging
  (`log_public_resolver_status`)

The proxy and the renewal service simply do **not** use it yet.

### Change 1 — extract the self-check into a shared module

`_dns_selfcheck`, `_dns_propagation_timeout`, `_txt_present` and the two module
constants live inside the API layer (`orders.py`). Move them to a service-layer
module so the proxy service can import them without an API → service back-edge:

```
backend/services/acme/dns_selfcheck.py   (new)
```

Proposed surface:

| Symbol | Origin | Note |
|--------|--------|------|
| `DNS_SELFCHECK_INTERVAL = 5` | `orders._DNS_SELFCHECK_INTERVAL` | unchanged |
| `DNS_SELFCHECK_DEFAULT_TIMEOUT = 120` | `orders._DNS_SELFCHECK_DEFAULT_TIMEOUT` | unchanged |
| `dns_propagation_timeout(config_key=...)` | `orders._dns_propagation_timeout` | parametrized config key |
| `wait_for_challenges(challenges, timeout)` | `orders._dns_selfcheck` | verbatim logic |
| `wait_for_txt(name, value, timeout)` | new thin wrapper | single-record variant for the proxy |

`orders.py` keeps thin aliases re-importing from the new module, so the client
behaviour and its tests (`backend/tests/test_acme_dns_selfcheck.py`) are
**unchanged**.

### Change 2 — proxy `_bg_respond_challenge()`

Replace the blind sleep with a bounded active poll, and **do not** trigger the
upstream validation if the record never became visible:

```python
from services.acme.dns_selfcheck import dns_propagation_timeout, wait_for_txt

# after provider.create_txt_record(zone, full_record_name, txt_value)
timeout = dns_propagation_timeout()          # see config decision below
if timeout == 0:
    logger.info("[ACME Proxy BG] DNS propagation wait skipped (timeout=0)")
else:
    check = wait_for_txt(full_record_name, txt_value, timeout)
    if not check["ok"]:
        logger.error(
            "[ACME Proxy BG] DNS TXT not visible after %ss for %s (%s) — "
            "not submitting upstream",
            timeout, domain, full_record_name,
        )
        self._delete_order_txt_records(order)   # extracted helper, see note
        entry = order.challenges_dict.get(chall_url, {})
        entry["status"] = "dns_not_ready"
        order.set_challenges_dict({**order.challenges_dict, chall_url: entry})
        db.session.commit()
        return
    logger.info("[ACME Proxy BG] DNS TXT confirmed after %ss", check["waited"])

# … existing "store record info for cleanup" + trigger upstream validation …
```

Notes:

- `full_record_name` is the FQDN of the challenge record
  (`_acme-challenge.<domain>`), already computed via
  `provider.get_acme_challenge_name(domain)`
- `txt_value` is already the SHA-256 digest of the upstream `key_authz`
- This runs in the background thread, so it is **not** bound by any HTTP
  worker timeout — the full configured timeout (up to 3600 s) is honored
- **Cleanup helper**: the TXT-deletion loop currently lives **inline** inside
  `get_certificate()` (iterating `order.dns_records_created` and calling
  `provider.delete_txt_record(...)`). Extract it into a private
  `_delete_order_txt_records(order)` and call it from **both** the success
  path (`get_certificate`) and this new failure path, so a propagation miss no
  longer leaves an orphan TXT record behind. On this failure path the record
  metadata is not persisted yet, so the helper must delete the just-created
  record directly (zone + `full_record_name`) even when `dns_records_created`
  is still empty.

### Change 3 — renewal service

`backend/services/acme_renewal_service.py` has the same fixed
`time.sleep(30)` before submitting challenges. Swap it for
`wait_for_challenges()` over the renewal challenge set, so slow zones stop
producing spurious renewal failures.

### Configuration decision

| Option | Config key | Trade-off |
|--------|-----------|-----------|
| **A (recommended)** | reuse `acme.client.dns_propagation_timeout` | one operator setting for all server-side DNS waits; already exposed in the ACME settings UI |
| B | new `acme.proxy.dns_propagation_timeout` | proxy tunable independently from the direct client, at the cost of a second knob + migration + UI field |

Recommendation: **Option A**. The Actalis deployment already runs the client
with a 300 s timeout; the proxy and renewal paths would inherit a sane value
immediately, and `timeout=0` preserves today's "submit right away" behaviour.

### Error semantics

Today a propagation miss still submits upstream and leaves the TXT record
behind. With the self-check:

```
create TXT ─► poll DNS ─► visible?  ── yes ─► POST upstream challenge ─► poll authz
                          │
                          └─ no (timeout) ─► cleanup TXT ─► mark dns_not_ready ─► stop
```

`dns_not_ready` lets the external client stop polling a stuck `processing`
challenge and retry with a fresh order, instead of hanging until the CA's own
authz expiry.

### Tests

| File | Content |
|------|---------|
| `backend/tests/test_acme_proxy_dns_selfcheck.py` (new) | TXT visible → upstream `POST` is issued |
| | timeout reached → upstream `POST` is **not** issued + TXT cleaned up + `dns_not_ready` |
| | `timeout=0` → immediate submit (legacy behaviour) |
| `backend/tests/test_acme_dns_selfcheck.py` (existing) | must still pass after the module extraction (client regression) |

### Expected behaviour after the change (Actalis)

```
T+0s    PUT TXT via DNS provider
T+0–5s  poll authoritative NS → not yet
T+~10s  TXT visible on authoritative NS → "confirmed via authoritative"
T+~10s  POST upstream challenge   (instead of a blind 30 s wait)
T+~24s  upstream authz valid
```

vs. today: if propagation exceeds 30 s the upstream `POST` fires against a
record that is not yet visible → intermittent `unauthorized`.

### Effort (this quick win only)

| Step | Effort |
|------|--------|
| Extract `dns_selfcheck.py` + re-wire `orders.py` | ~1 h |
| Proxy branch + cleanup + `dns_not_ready` | ~1.5 h |
| Renewal service swap | ~0.5 h |
| Tests | ~1 h |

**Total:** ~half a day, shippable **before** any HTTP-01 work.

## Estimated effort

| Phase | Effort | Content |
|-------|--------|---------|
| 0 | ~0.5 d | **Active DNS self-check** (replace both 30 s sleeps) — independent quick win |
| 1 | ~2–3 d | Config + synthetic `get_authz` + `respond_challenge` HTTP branch |
| 2 | ~1–2 d | `validate_client_http01` + `_bg_respond_challenge` chaining |
| 3 | ~1 d | Wire the self-check into the HTTP-01 chain + error handling |
| 4 | ~1 d | UI + i18n + docs |
| 5 | ~1–2 d | E2E tests (Certbot `--preferred-challenges http`) |

**Total:** ~6–9 days of dev + tests (phase 0 can land on its own).

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
