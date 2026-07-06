# Issue Certificate — SAN types & EC curves — test plan

Extends [#167](https://github.com/NeySlim/ultimate-ca-manager/issues/167) / [#168](https://github.com/NeySlim/ultimate-ca-manager/pull/168) to **Émettre un certificat** (`POST /api/v2/certificates`).

## Fixes

- **Typed SAN enforcement**: FQDN in IP field → HTTP 400 (no silent DNS reclassification)
- **EC curves**: `ecdsa` + `256` / `NIST P-384` / UI labels → `prime256v1` / `secp384r1` / `secp521r1`
- **CN auto-SAN**: email CN (`fred@fred.fr`) is **not** auto-added as DNS on server certs; use **Email** or **Combined** cert type for email SAN
- **i18n**: validation messages under `certificates.san*` (9 locales); CSR key labels under `csrs.key*`

## Automated tests

```bash
cd backend
pytest tests/test_san_parse.py::TestParseCertSanPayload -v
pytest tests/test_san_parse.py::TestAutoSanFromCn -v
pytest tests/test_key_type.py::TestParseIssueKeyType -v
pytest tests/test_certificates.py::TestCreateCertificate -v

cd ../frontend
npm test -- --run src/lib/__tests__/sanValidate.test.js
```

## Manual (UI)

1. **Certificates** → **Issue Certificate**
2. Type **Serveur**, CN `fred@fred.fr` → no auto DNS SAN row (empty auto-SAN block)
3. Type **Email**, same CN → auto **email** SAN `fred@fred.fr`
4. Add SAN type **IP** with `www.example.com` → client error (translated)
5. Key type **ECDSA** + **NIST P-521** → certificate issued
