# ACME — Vhost public, URLs directory et certificats wildcard

UCM peut annoncer des URLs ACME publiques distinctes de l’URL d’administration.
Ce document décrit la topologie recommandée (noms `example.com` uniquement),
les règles des certificats wildcard, le plan de test et les commandes pytest.

Voir aussi : [ACME-PROXY-MULTI-CA.md](./ACME-PROXY-MULTI-CA.md), [ACME-DNS-PROPAGATION.md](./ACME-DNS-PROPAGATION.md).

## Topologie de référence

| Rôle | FQDN | Usage |
|------|------|--------|
| **Admin UCM** | `https://admin.ucm.example.com:8443` | GUI, API session, mTLS client optionnel/obligatoire |
| **ACME public** | `https://acme.example.com:8443` | `/acme/*` (CA locale) et `/acme/proxy/*` (proxy vers CA externe) |
| **URL de base UCM** (Paramètres → Général) | `https://admin.ucm.example.com` | Liens absolus, notifications, SAML |

Le listener UCM (gunicorn) est unique ; en production, un **reverse proxy** (F5, nginx, Traefik) termine TLS par **vhost** et route vers le backend UCM.

### Paramètres UCM (Paramètres → Général)

| Clé `SystemConfig` | Exemple | Effet |
|--------------------|---------|--------|
| `acme_proxy_vhost` | `acme.example.com` | Hostname dans les URLs du directory ACME (`newOrder`, `newNonce`, …) |
| `acme_proxy_port` | `8443` | Port dans ces URLs (omis si `443`) |
| `acme_proxy_tls_cert_id` | ID certificat UCM | **Métadonnée** : cert TLS à déployer sur le vhost ACME côté proxy (non appliqué au runtime gunicorn) |

Sans `acme_proxy_vhost`, UCM retombe sur `scheme://Host` de la requête entrante.

## Certificats wildcard — règles essentielles

Un SAN wildcard `*.example.com` ne couvre **qu’un seul** label à gauche de `example.com`.

| Hostname accédé | Cert `*.example.com` | Cert `*.ucm.example.com` | Cert SAN explicites `admin.ucm.example.com` + `acme.example.com` |
|-----------------|----------------------|--------------------------|------------------------------------------------------------------|
| `acme.example.com` | ✅ | ❌ | ✅ |
| `admin.ucm.example.com` | ❌ | ✅ | ✅ |
| `ucm.example.com` (apex) | ❌ | ❌ | ❌ (sauf SAN apex dédié) |
| `api.ucm.example.com` | ❌ | ✅ | ❌ (sauf SAN dédié) |

### Erreurs fréquentes

1. **Appliquer `*.example.com` sur le vhost admin**  
   Le navigateur accède à `admin.ucm.example.com` → deux labels avant `example.com` → **hostname mismatch**.

2. **Appliquer `*.ucm.example.com` sur le vhost ACME `acme.example.com`**  
   `acme.example.com` n’est pas sous `*.ucm.example.com` → **hostname mismatch**.

3. **Configurer `acme_proxy_vhost=acme.example.com` sans DNS ni TLS alignés**  
   Certbot / curl time-out ou échouent en TLS alors que UCM répond en local sur un autre nom.

4. **Confondre URL directory et certificat serveur**  
   Les URLs dans le directory suivent `acme_proxy_vhost` ; le client ACME vérifie le certificat TLS **du hostname de chaque URL** annoncée.

### Stratégies TLS recommandées

**Option A — Deux vhosts proxy (recommandé prod)**

```
admin.ucm.example.com:8443  → cert SAN admin.ucm.example.com (ou *.ucm.example.com)
acme.example.com:8443       → cert SAN acme.example.com (ou *.example.com)
                              → pas de mTLS client
```

**Option B — Un certificat multi-SAN**

```
SAN: admin.ucm.example.com, acme.example.com
```

**Option C — Lab / single-node**

Utiliser temporairement le même FQDN pour admin et ACME (ex. `admin.ucm.example.com`) le temps de valider le flux ACME, puis scinder.

## Configuration exemple

### UCM (GUI ou API)

```http
PATCH /api/v2/settings/general
{
  "base_url": "https://admin.ucm.example.com",
  "acme_proxy_vhost": "acme.example.com",
  "acme_proxy_port": 8443,
  "acme_proxy_tls_cert_id": 42
}
```

`acme_proxy_tls_cert_id` référence le certificat géré dans UCM à installer sur le vhost `acme.example.com` du reverse proxy.

### DNS

```
admin.ucm.example.com.  A     203.0.113.10
acme.example.com.       A     203.0.113.10
```

Même IP possible ; le proxy distingue par **SNI / Host**.

### Certbot (proxy multi-CA)

```bash
certbot certonly \
  --server https://acme.example.com:8443/acme/proxy/actalis-production/directory \
  --preferred-challenges dns-01 \
  --authenticator manual \
  --manual-auth-hook /path/to/auth.sh \
  --manual-cleanup-hook /path/to/cleanup.sh \
  --non-interactive --agree-tos \
  -m operator@example.com \
  -d app.example.com
```

Prérequis : `acme.example.com` résout vers le proxy, cert TLS valide pour ce nom, pas de mTLS client requis sur ce vhost.

## Tests automatisés (pytest)

### Suite ciblée (non-régression vhost public)

```bash
cd backend
python -m pytest tests/test_acme_public_url.py -q
python -m pytest tests/test_acme.py::TestAcmeServerSettings::test_get_settings_exposes_configured_public_acme_base_url \
  tests/test_acme.py::TestAcmeClientSettings::test_get_client_settings_exposes_configured_public_acme_urls \
  -q
```

### Couverture

| Fichier | Scénarios |
|---------|-----------|
| `test_acme_public_url.py` | `get_acme_public_origin`, port 443 vs non défaut, fallback Host, **table wildcard SAN**, directory `/acme` et `/acme/proxy` |
| `test_acme.py` | Settings API `acme_public_base_url` / `acme_proxy_public_base_url` |

### Commande suite ACME élargie

```bash
cd backend
python -m pytest tests/test_acme_public_url.py \
  tests/test_acme_proxy_ca_account.py \
  tests/test_acme_dns_selfcheck.py \
  tests/test_acme.py::TestAcmeServerSettings \
  tests/test_acme.py::TestAcmeClientSettings \
  tests/test_acme.py::TestAcmeClientProxy \
  -q
```

## Plan de test manuel

### 1. Paramètres généraux

1. Paramètres → Général : `acme_proxy_vhost` = `acme.example.com`, port `8443`
2. Enregistrer → recharger la page → valeurs persistées
3. ACME → Configuration : directory affiché `https://acme.example.com:8443/acme/directory`
4. ACME → Let's Encrypt : proxy URL `https://acme.example.com:8443/acme/proxy/...`

### 2. DNS et TLS

1. `dig +short acme.example.com` → IP du proxy attendue
2. `openssl s_client -connect acme.example.com:8443 -servername acme.example.com`  
   → SAN contient `acme.example.com` ou wildcard compatible (`*.example.com`)
3. `curl -sk https://acme.example.com:8443/acme/proxy/directory` → JSON directory, URLs cohérentes

### 3. Admin TLS (wildcard `*.ucm.example.com`)

1. Appliquer un cert `*.ucm.example.com` **uniquement** sur le vhost `admin.ucm.example.com`
2. Ouvrir `https://admin.ucm.example.com:8443` → pas d’erreur certificat
3. Vérifier que le **même** cert wildcard n’est **pas** utilisé seul pour `acme.example.com`

### 4. Certbot E2E

1. Compte proxy activé (slug ex. `actalis-production`)
2. Lancer certbot avec `--server https://acme.example.com:8443/acme/proxy/<slug>/directory`
3. Attendu : enregistrement compte OK, challenge DNS-01 soumis (échec seulement si hook DNS absent)

### 5. Régression apex wildcard

1. Certificat CN=`*.ucm.example.com`, SAN=`*.ucm.example.com` seulement
2. Tenter HTTPS sur `https://ucm.example.com` → **doit** échouer (apex non couvert)
3. Documenter pour l’équipe ops : wildcard ≠ apex

## Critères d’acceptation

- [ ] `acme_public_base_url` et liens directory utilisent `acme.example.com` configuré
- [ ] Admin reste sur `admin.ucm.example.com` avec cert compatible
- [ ] Certbot atteint le directory sans timeout ni hostname mismatch
- [ ] Tests `test_acme_public_url.py` verts
- [ ] Aucun hostname de production réel dans les commits doc (uniquement `example.com`)

## Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| `ConnectTimeout` vers `acme.example.com` | DNS vers mauvaise IP / pare-feu | Corriger enregistrement A/AAAA, ouvrir :8443 |
| `Hostname mismatch` | Cert wildcard ou SAN incorrect pour le vhost | Cert dédié ou multi-SAN (voir table ci-dessus) |
| Directory OK en curl local, Certbot échoue | URLs directory pointent vers autre hostname que le TLS servi | Aligner `acme_proxy_vhost` + cert proxy |
| GUI OK, ACME KO après changement cert HTTPS | Cert admin appliqué sur listener unique sans split vhost | Restaurer cert admin ; terminer TLS ACME sur le proxy |
