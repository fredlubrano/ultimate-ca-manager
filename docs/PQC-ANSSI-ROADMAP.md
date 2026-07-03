# Roadmap PQC — alignement ANSSI (fork)

> Document de travail **fork uniquement** (`fredlubrano/ultimate-ca-manager`).  
> Ne remplace pas la roadmap upstream ; prépare la transition post-quantique conforme aux
> recommandations françaises ([FAQ PQC ANSSI](https://cyber.gouv.fr/enjeux-technologiques/cryptographie-post-quantique/faq-pqc/),
> [Avis migration 2023](https://messervices.cyber.gouv.fr/documents-guides/Avis%20de%20l'ANSSI%20sur%20la%20migration%20vers%20la%20cryptographie.pdf)).

---

## 1. Objectif

Préparer UCM à une future émission **hybride** (classique + PQC) de CA et certificats internes,
en commençant par la **mise à jour des bibliothèques crypto** — prérequis technique avant toute
feature UI/API.

**Hors périmètre immédiat** : ACME, Let's Encrypt, profils navigateur publics.

---

## 2. Mises à jour de bibliothèques

### 2.1 État actuel (upstream `dev`)

| Composant | Version pin | Usage réel dans UCM |
|-----------|-------------|---------------------|
| `cryptography` | `48.0.1` | **PKI complète** : génération clés, CSR, X.509, PKCS#12, OCSP, ACME, mTLS, import |
| `pyOpenSSL` | `26.2.0` | Déclaré dans `requirements.txt` ; **aucun `import OpenSSL`** dans le backend |
| `openssl` CLI | système (packaging) | Export P7B (`crl2pkcs7`) uniquement |
| TLS runtime | `ssl` stdlib + Gunicorn | Listener HTTPS |

Quasi toute la pile PKIX repose sur **`cryptography`** (hazmat + `x509`), pas sur pyOpenSSL.

### 2.2 Cible proposée

| Composant | Version cible | Motif |
|-----------|---------------|-------|
| `cryptography` | **`49.0.0`** | FIPS 203/204/205 exposés en API : ML-KEM, ML-DSA, SLH-DSA ; PKIX ML-DSA |
| `pyOpenSSL` | **`26.3.0`** *ou retrait* | Alignement avec `cryptography` 49 si conservé ; sinon suppression (dead dependency) |

**Patch `requirements.txt` minimal :**

```diff
 # Cryptography & OpenSSL
-cryptography==48.0.1
+cryptography==49.0.0
 argon2-cffi>=23.1.0
-pyOpenSSL==26.2.0
+pyOpenSSL==26.3.0
```

*Alternative recommandée après audit : retirer `pyOpenSSL` si aucun import indirect ne le requiert.*

### 2.3 Pourquoi `cryptography` 49 (et pas rester en 48)

1. **Normes NIST finalisées (août 2024)** — FIPS 203 (ML-KEM), 204 (ML-DSA), 205 (SLH-DSA) ; l’ANSSI s’y réfère explicitement.
2. **ML-DSA en PKIX** — génération / chargement de certificats X.509 ML-DSA (spike lab validé sur Python 3.13).
3. **Alignement calendrier ANSSI** — obligation PQC en qualification à partir de **2027** ; achats sans PQC déconseillés après **2030**.
4. **Pas de régression** — validation sur environnement de lab privé : **2032 tests pytest passés**, health OK (voir §4).
5. **Crypto-agilité** — l’ANSSI exige la capacité à changer de jeux de paramètres PQC ; la 49 ouvre cette voie sans fork de code bas niveau.

**Ce que la 49 ne résout pas seule** : formats de certificats **hybrides** PKI/IGC (travaux ANSSI / IETF encore en cours).

### 2.4 Pourquoi traiter `pyOpenSSL`

- Non utilisé dans le code applicatif → risque de **dérive de versions** et surface CVE sans bénéfice.
- Si conservé : **`26.3.0`** pour compatibilité wheels avec `cryptography` 49.
- PR suggérée en **deux temps** : (1) bump + tests, (2) chore retrait pyOpenSSL si audit confirmé.

### 2.5 Dépendances à surveiller (pas de bump requis au premier PR)

| Paquet | Lien PQC | Action |
|--------|----------|--------|
| `pkilint` | Lint RFC 5280 / CAB Forum | Vérifier prise en charge ML-DSA / certs hybrides avant activation prod |
| `josepy` / ACME | Hors périmètre PQC interne | Inchangé dans le premier lot |
| `python-pkcs11` / HSM | Signatures hybrides futures | Feuille de route fournisseur HSM à inventorier |
| `openssl` CLI | P7B legacy | Suffisant pour l’existant ; PQC PKCS#7 = chantier séparé |

### 2.6 OpenSSL système (hors pip)

Le lab tourne avec **OpenSSL 3.5.x** système. Les wheels `cryptography` embarquent leurs bindings Rust/OpenSSL ;
le binaire `openssl` du OS reste requis pour `crl2pkcs7`. Documenter la version minimale dans les notes de release.

---

## 3. Doctrine ANSSI appliquée à UCM

### 3.1 Hybridation (règle centrale)

L’ANSSI exige l’**hybridation** classique + PQC dès qu’une protection post-quantique est pertinente,
sauf signatures **hash-based** seules (SLH-DSA, XMSS, LMS).

| Cas d’usage UCM | Recommandation ANSSI | Implication produit |
|-----------------|----------------------|---------------------|
| CA racine / intermédiaire | Sig hybride (ex. ECDSA P-384 + ML-DSA-65) | Pas de « CA ML-DSA seule » en prod alignée FR |
| Certificat serveur / client | Idem | Deux chaînes de confiance / double signature à documenter |
| TLS listener UCM | ML-KEM hybride + courbe classique (CatKDF/CasKDF) | Phase ultérieure (Gunicorn / reverse proxy) |
| Archivage / code signing long terme | SLH-DSA possible sans hybride obligatoire | Option tardive |

### 3.2 Paramètres algorithmiques

| Rôle | Algorithme | Paramètre ANSSI |
|------|------------|-----------------|
| Signature PKI | ML-DSA (FIPS 204) | **Niveau 3** (`ML-DSA-65`) minimum ; **niveau 5** (`ML-DSA-87`) si politique stricte |
| KEM (TLS) | ML-KEM (FIPS 203) | Niveau 3 (`ML-KEM-768`) ou 5 ; clés éphémères ; IND-CCA2 |
| Plan B signature | SLH-DSA (FIPS 205) | Hybridation facultative |

Partenaire classique hybride : **ECDSA P-384** ou **RSA-3072/4096** (non-régression).

### 3.3 PKI / formats certificats

> *« L’ANSSI mène aujourd’hui des travaux […] sur la PKI/IGC et notamment le format des certificats. »* — FAQ PQC

**Conséquence** : la feature UCM doit démarrer par un **feature flag** et un mode **expérimental lab** ;
pas de promesse de compatibilité navigateur / clients TLS tant que les profils hybrides ne sont pas stabilisés.

### 3.4 Calendrier indicatif (organisation + produit)

| Échéance | Action |
|----------|--------|
| **2026** | Inventaire crypto UCM ; bump `cryptography` 49 ; spikes ML-DSA |
| **2027** | Référentiels ANSSI qualification PQC ; exigences sur nouveaux déploiements sensibles |
| **2030** | Ne plus déployer de PKI sans capacité PQC hybride |
| **2035** | Alignement feuille de route UE (transition large) |

---

## 4. Validation lab (fork, pré-upstream)

Environnement : instance lab privée (`/opt/ucm/`), Python 3.13, OpenSSL 3.5.6.

| Étape | Résultat |
|-------|----------|
| `pip install cryptography==49.0.0 pyOpenSSL==26.3.0` | OK |
| `systemctl restart ucm` | `active` |
| `GET /health` | 200 |
| `pytest` complet | **2032 passed**, 6 skipped |
| Spike ML-DSA-65 cert auto-signé | OK |
| Spike ML-KEM-768 encapsulate/decapsulate | OK (API 49 : tuple `(shared_secret, ciphertext)`) |

**Rollback lab :**

```bash
pip install "cryptography==48.0.1" "pyOpenSSL==26.2.0" && systemctl restart ucm
```

---

## 5. Découpage PR (fork → proposition upstream)

### PR A — `chore(deps): cryptography 49 + pyOpenSSL 26.3` (prioritaire)

- Fichier : `backend/requirements.txt`
- Tests : CI complète + smoke PKI (émission RSA/EC, export PEM/P12/P7B, OCSP)
- Description : lien vers ce document + résultats lab §4
- **Pourquoi** : prérequis normatif ANSSI/NIST sans changer le comportement fonctionnel actuel

### PR B — `chore(deps): remove unused pyOpenSSL` (optionnel)

- Audit `pip show` / imports transitifs
- Retrait ligne `pyOpenSSL` si confirmé inutile

### PR C — `feat(pqc): hybrid CA/certificate issuance` (feature flag, branche séparée)

*Après merge PR A.*

| Zone | Travail |
|------|---------|
| Backend | `KEY_TYPES` + ML-DSA-65/87 ; génération hybride ; politiques |
| API v2 | `key_algo` / `pqc_profile` ; validation ANSSI (rejeter PQC seul hors hash-based) |
| Frontend | Options CA / émission cert ; avertissements compat |
| Tests | Vecteurs ML-DSA ; non-régression RSA/EC |
| i18n | Clés `pqc.*`, `hybrid.*` |
| Docs | Mise à jour `SECURITY.md`, guide admin |

---

## 6. Inventaire pré-migration (checklist ops)

Aligné FAQ ANSSI — à faire côté déploiement avant PR C :

- [ ] Lister toutes les CA et certificats RSA/EC et leur **durée de vie post-2030**
- [ ] Identifier clients TLS, mTLS, SCEP, EST dépendants des algos actuels
- [ ] Contacter éditeurs HSM (PKCS#11) pour roadmap ML-DSA / hybride
- [ ] Classer les cas : critique / standard / lab
- [ ] Intégrer exigence PQC hybride dans les cycles d’achat à partir de 2028

---

## 7. Références

| Document | URL |
|----------|-----|
| FAQ PQC ANSSI | https://cyber.gouv.fr/enjeux-technologiques/cryptographie-post-quantique/faq-pqc/ |
| Avis migration 2022 | https://cyber.gouv.fr/publications/avis-de-lanssi-sur-la-migration-vers-la-cryptographie-post-quantique |
| Suivi 2023 (hybridation, algorithmes) | https://messervices.cyber.gouv.fr/documents-guides/Avis%20de%20l'ANSSI%20sur%20la%20migration%20vers%20la%20cryptographie.pdf |
| NIST PQC project | https://csrc.nist.gov/projects/post-quantum-cryptography |
| FIPS 203 / 204 / 205 | ML-KEM / ML-DSA / SLH-DSA |
| Feuille de route UE PQC (juin 2025) | Co-pilotée ANSSI / BSI / NCSC-NL |

---

## 8. Notes fork

- Branche doc : `docs/pqc-anssi-deps-roadmap`
- Issue de suivi : voir dépôt `fredlubrano/ultimate-ca-manager`
- Ne pas inclure de trailer `Co-authored-by: Cursor` dans les commits destinés à upstream
