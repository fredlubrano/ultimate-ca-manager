# ACME Proxy Multi-CA — Plan de test

Feature: le proxy ACME réutilise les comptes `AcmeClientAccount` (même registre que le client ACME) via `acme.proxy.acme_account_id`.

## Prérequis lab

- UCM déployé avec migration `050_acme_proxy_ca_account_link`
- Au moins un compte CA externe (ex. Let's Encrypt Staging)
- Droits `read:acme` / `write:acme`

## Tests automatisés (non-régression)

```bash
cd backend
python -m pytest tests/test_acme_proxy_ca_account.py \
  tests/test_acme_proxy_key_encrypted.py \
  tests/test_acme.py::TestAcmeClientProxy \
  tests/test_acme.py::TestAcmeClientSettings \
  -q
```

Couverture ciblée :

| Fichier | Scénarios |
|---------|-----------|
| `test_acme_proxy_ca_account.py` | Résolution compte, API settings, binding service |
| `test_acme_proxy_key_encrypted.py` | Chiffrement clé sur `AcmeClientAccount` |
| `test_acme.py` | Register/unregister proxy, champs settings |

## Tests manuels — UI

### 1. Sélection compte CA

1. ACME → Let's Encrypt → section **Proxy ACME**
2. Activer le proxy
3. Vérifier le sélecteur **Compte CA en amont** liste les comptes de **Comptes CA externes**
4. Choisir un compte → l'URL directory s'affiche sous le sélecteur
5. Recharger la page → sélection persistée

### 2. Test connexion

1. Avec un compte sélectionné, cliquer **Tester la connexion**
2. Attendu : ✓ connecté + nom CA (ex. Let's Encrypt Staging)
3. Sans compte sélectionné : bouton désactivé

### 3. Enregistrement upstream

1. Sélectionner un compte non enregistré (`is_registered: false`)
2. Saisir un email public (ex. `you@gmail.com`)
3. **Enregistrer le compte** → succès, badge « Compte enregistré »
4. Vérifier dans **Comptes CA externes** que le même compte affiche enregistré

### 4. Bascule entre CAs

1. Créer 2 comptes (Staging + Production)
2. Enregistrer les deux
3. Basculer le sélecteur proxy → `GET /api/v2/acme/client/settings` reflète `proxy_acme_account_id` et l'URL directory

### 5. Reset compte

1. Compte enregistré → icône reset (↻)
2. Confirmer → `account_url` / clé effacés sur le compte lié
3. Ré-enregistrer possible

## Tests manuels — API

```bash
# Settings
curl -sk -H "Authorization: Bearer $TOKEN" \
  https://ucm.pfcorp.eu:8443/api/v2/acme/client/settings | jq '.data | {proxy_acme_account_id, proxy_upstream_url, proxy_account_registered}'

# Sélection compte id=1
curl -sk -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"proxy_acme_account_id":1}' \
  https://ucm.pfcorp.eu:8443/api/v2/acme/client/settings

# Test connexion
curl -sk -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"acme_account_id":1}' \
  https://ucm.pfcorp.eu:8443/api/v2/acme/client/proxy/test-connection
```

## Tests manuels — Proxy ACME (E2E)

1. Activer proxy + compte Staging enregistré
2. `curl -sk https://<ucm>/acme/proxy/directory` → JSON directory UCM
3. Optionnel : certbot/pebble client pointant vers `/acme/proxy/directory` (DNS-01 via UCM)

## Migration legacy (upgrade)

Sur instance avec ancienne config proxy (`acme.proxy.account_key` / mode staging) :

1. Appliquer migration 050 au démarrage
2. Vérifier `acme.proxy.acme_account_id` renseigné
3. Proxy fonctionne sans re-saisie EAB/mode

## Critères d'acceptation

- [ ] Sélection multi-CA dans l'UI proxy
- [ ] Un seul registre de comptes (pas de duplication EAB proxy)
- [ ] Tests pytest ciblés verts
- [ ] Migration 050 appliquée sur lab
- [ ] `/acme/proxy/directory` répond après bascule de compte
