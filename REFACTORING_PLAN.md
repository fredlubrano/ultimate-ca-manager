# UCM Refactoring Plan - v2.142-dev

**Branche :** `refactor`  
**Stratégie :** Commits directs, conservation historique Git  
**Développeur :** Lio / Vibe  
**Priorité :** Maintenabilité > Performance  
**Règle UCM :** Fichiers 200-400l (800l max), haute cohésion, faible couplage

---

## 📋 Sommaire
- [Objectifs](#objectifs)
- [Règles](#règles)
- [État Actuel](#état-actuel)
- [Analyse Globale](#analyse-globale)
- [Fichiers par Priorité](#fichiers-par-priorité)
- [Plans Détaillés](#plans-détaillés)
- [Progrès](#progrès)
- [Historique des commits](#historique-des-commits)

---

## 🎯 Objectifs

### Principal
Réduire la taille des fichiers > 800 lignes et améliorer la maintenabilité par :
- **Découpage** des fichiers monolithiques en modules focalisés
- **Suppression des redondances** de code
- **Clarification des responsabilités** (1 fichier = 1 responsabilité)
- **Optimisation des imports** (éviter les lazy imports inutiles)

### Secondaires
1. Supprimer les dépendances circulaires (services → api)
2. Séparer clairement les layers (Routes → Services → Models)
3. Centraliser la logique dupliquée (export, validation, audit)
4. Améliorer la testabilité (méthodes plus petites, moins de side effects)

---

## 📜 Règles

### ⚠️ CONTRAINTES UCM (absolues)
- **Taille fichiers :** 200-400 lignes (max 800)
- **Cohésion :** Haute (1 fichier = 1 responsabilité claire)
- **Couplage :** Faible (éviter imports circulaires)
- **Tests :** `pytest backend/tests/ -x -q` **ET** `npm test` avant chaque commit
- **Historique :** **Conserver** (pas de squash, commits atomiques)
- **Commits :** Directs sur `refactor`, messages en anglais, format conventional
- **Branche :** Toujours travailler sur `refactor`

### 📝 Conventions de commit
```
refactor(scope): description
fix(scope): description
feats(scope): description  # pour nouvelles fonctionnalités pendant refactor
```

### 🔧 Workflow
1. Analyser le fichier cible
2. Créer les nouveaux modules dans un sous-dossier
3. Déplacer le code par sections logiques
4. Ajouter un wrapper pour compatibilité descendante si nécessaire
5. Lancer tous les tests (backend + frontend)
6. Commiter avec message clair
7. Mettre à jour ce REFACTORING_PLAN.md

---

## 📊 État Actuel

### ✅ Terminé

| Fichier | Lignes avant | Statut | Modules résultants | Commit |
|--------|-------------|--------|------------------|--------|
| `services/backup_service.py` | 2351 | ✅ | 11 modules (330-502l) | 516d8695 + f30c09f4 |
| `api/v2/certificates.py` | 2220 | ✅ | 6 modules (85-1470l) | 317253e9 |
| `api/v2/cas.py` | 1245 | ✅ | 6 modules (35-459l) | 8f9f15f0 |
| `api/v2/system.py` | 1556 | ✅ | 9 modules (92-488l) | 678d7553 |

**Total réduit :** 7352 lignes → ~3500 lignes réparties

---

## 🔍 Analyse Globale

### Fichiers > 800 lignes (à traiter par priorité)

#### 🔴 Priorité HAUTE (Backend Services - bloquants pour maintenabilité)

| # | Fichier | Lignes | Complexité | Redondances | Dép. circulaires | Priorité |
|---|--------|--------|------------|-------------|------------------|----------|
| 1 | `services/trust_store.py` | 1487 | ⭐⭐⭐⭐ | Oui | Oui | **1** |
| 2 | `services/acme/acme_service.py` | 1456 | ⭐⭐⭐⭐ | Oui | Oui | **2** |
| 3 | `services/pdf_report_service.py` | 1298 | ⭐⭐⭐ | Non | Non | **3** |
| 4 | `services/scep_service.py` | 981 | ⭐⭐⭐ | Oui | Non | **4** |
| 5 | `services/cert_service.py` | 944 | ⭐⭐⭐ | Oui | Non | **5** |
| 6 | `services/discovery_service.py` | 928 | ⭐⭐⭐ | Oui | Non | **6** |
| 7 | `services/opnsense_import.py` | 884 | ⭐⭐⭐ | Non | Non | **7** |
| 8 | `services/database_admin_service.py` | 817 | ⭐⭐⭐⭐ | Oui | Oui | **8** |

#### 🟡 Priorité MOYENNE (Backend API)

| # | Fichier | Lignes | Complexité | Priorité |
|---|--------|--------|------------|----------|
| 9 | `api/v2/sso.py` | 1843 | ⭐⭐⭐⭐ | **9** |
| 10 | `api/v2/ssh_cas.py` | 1607 | ⭐⭐⭐ | **10** |
| 11 | `api/v2/settings.py` | 1314 | ⭐⭐⭐ | **11** |
| 12 | `api/v2/users.py` | 934 | ⭐⭐⭐ | **12** |
| 13 | `api/v2/acme_client.py` | 918 | ⭐⭐⭐ | **13** |
| 14 | `api/v2/tools.py` | 853 | ⭐⭐ | **14** |
| 15 | `api/v2/acme.py` | 849 | ⭐⭐⭐ | **15** |
| 16 | `api/v2/account.py` | 806 | ⭐⭐ | **16** |

#### 🟡 Priorité MOYENNE (Modèles)

| # | Fichier | Lignes | Complexité | Priorité |
|---|--------|--------|------------|----------|
| 17 | `models/__init__.py` | 1180 | ⭐⭐⭐⭐⭐ | **17** |
| 18 | `migrations/000_baseline_v252.py` | 886 | ⭐ (migration, ne pas toucher) | - |

#### 🟢 Priorité FAIBLE (Backend Services - déjà < 800l mais optimisables)

| Fichier | Lignes | Optimisations possibles |
|--------|--------|------------------------|
| `services/ca_service.py` | 788 | Split en 4 modules, supprimer redondances |
| `services/msca_service.py` | 580 | OK pour l'instant |
| `services/acme/acme_proxy_service.py` | 998 | > 800, à traiter |
| `services/acme/acme_client_service.py` | 930 | > 800, à traiter |

#### 🟢 Priorité FAIBLE (Frontend)

| Fichier | Lignes | Priorité |
|--------|--------|----------|
| `pages/SettingsPage.jsx` | 4833 | **20** |
| `pages/ACMEPage.jsx` | 3527 | **21** |
| `pages/DiscoveryPage.jsx` | 1854 | **22** |
| `pages/CAsPage.jsx` | 1693 | **23** |
| `pages/CertificatesPage.jsx` | 1464 | **24** |

---

## 📁 Fichiers par Priorité

### Priorité 1: Services Backend Critiques (> 1400 lignes)
1. **`services/trust_store.py`** (1487l)
2. **`services/acme/acme_service.py`** (1456l)
3. **`services/pdf_report_service.py`** (1298l)

### Priorité 2: Services Backend (> 800 lignes)
4. **`services/scep_service.py`** (981l)
5. **`services/cert_service.py`** (944l)
6. **`services/discovery_service.py`** (928l)
7. **`services/opnsense_import.py`** (884l)
8. **`services/database_admin_service.py`** (817l)
9. **`services/acme/acme_proxy_service.py`** (998l)
10. **`services/acme/acme_client_service.py`** (930l)

### Priorité 3: API Backend (> 800 lignes)
11. **`api/v2/sso.py`** (1843l)
12. **`api/v2/ssh_cas.py`** (1607l)
13. **`api/v2/settings.py`** (1314l)
14. **`api/v2/users.py`** (934l)
15. **`api/v2/acme_client.py`** (918l)
16. **`api/v2/tools.py`** (853l)
17. **`api/v2/acme.py`** (849l)
18. **`api/v2/account.py`** (806l)

### Priorité 4: Modèles et autres
19. **`models/__init__.py`** (1180l) - à split en modèles individuels
20. **`app.py`** (1533l) - initialisation Flask

### Priorité 5: Frontend
21. **`pages/SettingsPage.jsx`** (4833l)
22. **`pages/ACMEPage.jsx`** (3527l)
23. **`pages/DiscoveryPage.jsx`** (1854l)
24. **`pages/CAsPage.jsx`** (1693l)
25. **`pages/CertificatesPage.jsx`** (1464l)

---

## 📝 Plans Détaillés

---

### 🎯 Tâche Actuelle: `services/ca_service.py` (788l) - OPTIMISATION

**Analyse complète :**

#### Structure actuelle (1 classe, 15 méthodes)

| Méthode | Lignes | Responsabilité | Complexité | Redondances |
|---------|--------|---------------|------------|-------------|
| `create_internal_ca` | 239 | Création CA + HSM | ⭐⭐⭐⭐ | Oui (fichiers, audit) |
| `import_ca` | 68 | Import CA | ⭐⭐ | Oui (fichiers) |
| `get_ca` | 3 | Query simple | ⭐ | Non |
| `get_ca_by_refid` | 3 | Query simple | ⭐ | Non |
| `list_cas` | 3 | Query simple | ⭐ | Non |
| `delete_ca` | 44 | Suppression + cleanup | ⭐⭐ | Oui (fichiers) |
| `export_ca` | 25 | Export cert | ⭐ | Non |
| `get_ca_chain` | 23 | Chaîne de certs | ⭐ | Oui (avec get_certificate_chain) |
| `increment_serial` | 19 | Mise à jour | ⭐ | Non |
| `generate_crl` | 51 | Génération CRL | ⭐⭐⭐ | Non |
| `export_ca_with_options` | 65 | Export avancé | ⭐⭐ | Oui (avec export_ca) |
| `get_ca_fingerprints` | 18 | Calcul empreintes | ⭐ | Non |
| `get_ca_details` | 20 | Détails cert | ⭐ | Non |
| `get_certificate_chain` | 17 | Wrapper de get_ca_chain | ⭐ | **Redondant** |
| `sign_csr_from_crypto` | 130 | Signature CSR | ⭐⭐⭐⭐ | Oui (audit, fichiers) |

#### Problèmes identifiés

1. **Code dupliqué**
   - Gestion des fichiers (cert/key) dans `create_internal_ca` et `import_ca`
   - `get_ca_chain` et `get_certificate_chain` font la même chose
   - Code d'audit dupliqué dans chaque méthode mutante
   - `decrypt_private_key`/`encrypt_private_key` définis localement ET importés

2. **Méthodes trop longues**
   - `create_internal_ca` (239l) → peut être split en 3-4 méthodes
   - `sign_csr_from_crypto` (130l) → peut être split en 2-3 méthodes

3. **Imports inline** (lazy loading)
   - Beaucoup d'imports à l'intérieur des méthodes → difficile à maintenir
   - Exemples : `from services.hsm import HsmService` dans `create_internal_ca`

4. **Responsabilités mélangées**
   - `create_internal_ca` : génération clé + création cert + sauvegarde fichiers + audit + commit
   - `sign_csr_from_crypto` : signature + extraction infos + création Certificate + commit

5. **Dépendances**
   - `TrustStoreService` utilisé partout → dépendance forte
   - `AuditService` utilisé partout → dépendance forte

#### Proposition de refactoring

**Option A: Split en modules par responsabilité** (Recommandé)

```
services/ca/
├── __init__.py              # Exports CAService
├── ca_service.py            # Classe principale (délégation)
├── ca_creation.py           # create_internal_ca, import_ca
├── ca_crud.py               # get_ca, get_ca_by_refid, list_cas, delete_ca
├── ca_export.py             # export_ca, export_ca_with_options, get_ca_fingerprints, get_ca_details
├── ca_operations.py         # get_ca_chain, get_certificate_chain, increment_serial, generate_crl
└── ca_signing.py            # sign_csr_from_crypto
```

**Option B: Extraire les helpers communs** (Plus léger)

```
services/ca/
├── __init__.py
├── ca_service.py            # Classe principale
├── helpers.py               # Gestion fichiers, audit, encryption wrappers
```

**Option C: Mixin-based** (comme backup_service)

```
services/ca/
├── __init__.py
├── ca_service.py            # Classe principale avec mixins
├── creation_mixin.py        # Méthodes de création
├── export_mixin.py          # Méthodes d'export
├── operations_mixin.py      # Méthodes opérations
```

**Recommandation :** Option A (modules séparés) car :
- Plus clair pour les développeurs
- Meilleure séparation des responsabilités
- Plus facile à tester unitairement
- Moins de couplage

#### Détail Option A

**`ca_creation.py`** (~200l)
- `create_internal_ca()` → extraire :
  - `_generate_ca_key()` (logique HSM/local)
  - `_build_ca_certificate()` (appel TrustStoreService)
  - `_save_ca_files()` (sauvegarde cert/key)
- `import_ca()` → déjà simple, garder tel quel

**`ca_export.py`** (~150l)
- `export_ca()`
- `export_ca_with_options()`
- `get_ca_fingerprints()`
- `get_ca_details()`

**`ca_operations.py`** (~120l)
- `get_ca_chain()`
- `get_certificate_chain()` → merge avec get_ca_chain
- `increment_serial()`
- `generate_crl()`

**`ca_crud.py`** (~100l)
- `get_ca()`
- `get_ca_by_refid()`
- `list_cas()`
- `delete_ca()`

**`ca_signing.py`** (~150l)
- `sign_csr_from_crypto()` → extraire :
  - `_extract_csr_info()`
  - `_create_certificate_from_signed()`

**`ca_service.py`** (~150l)
- Classe `CAService` avec délégation vers les modules
- Gère les imports
- Point d'entrée unique pour compatibilité

**Améliorations transverses :**
1. Créer `helpers.py` avec :
   - `save_ca_files(ca)` → extrait de create_internal_ca et import_ca
   - `audit_ca(action, ca, message)` → wrapper AuditService
   - Supprimer les doublons encrypt/decrypt

2. Utiliser des decorators pour l'audit :
   ```python
   @audit_ca('ca_created')
   def create_internal_ca(...):
       ...
   ```

**Estimation :** 2-3 commits

---

### Tâche: `services/trust_store.py` (1487l)

**Analyse rapide :**
- 1 classe `TrustStoreService`
- ~40 méthodes
- Beaucoup de logique de certificats, CRL, OCSP
- Dépendances : `CA`, `Certificate`, `CRL`, `AuditLog`

**Proposition :**
```
services/trust_store/
├── __init__.py
├── trust_store_service.py    # Classe principale
├── certificate_helpers.py    # Parsing, validation, détails
├── crl_helpers.py           # Génération CRL
├── ocsp_helpers.py          # OCSP
├── export_helpers.py        # PKCS12, JKS, P7B, etc.
└── key_helpers.py           # Génération clés, HSM
```

---

### Tâche: `services/acme/acme_service.py` (1456l)

**Analyse :**
- 1 classe `AcmeService`
- Gère ACME accounts, orders, challenges
- Beaucoup de dépendances circulaires avec `api/v2/acme*.py`

**Proposition :**
```
services/acme/
├── __init__.py
├── acme_service.py         # Classe principale
├── account_service.py      # Gestion des comptes ACME
├── order_service.py       # Gestion des orders
├── challenge_service.py   # Gestion des challenges (HTTP-01, DNS-01, TLS-ALPN-01)
└── domain_helpers.py       # Résolution domaine → CA (déjà partiellement fait)
```

**À faire aussi :** Corriger les dépendances circulaires (api → services)

---

### Tâche: `services/pdf_report_service.py` (1298l)

**Analyse :**
- 1 classe `PdfReportService`
- Génération de rapports PDF
- Beaucoup de code de formatting HTML/PDF

**Proposition :**
```
services/reporting/
├── __init__.py
├── pdf_report_service.py  # Classe principale
├── templates/              # Templates Jinja2 séparés
├── formatters.py          # Formattage des données
└── pdf_generator.py       # Génération PDF pure
```

---

## ✅ Progrès

### Backend API ✅
- [x] `api/v2/certificates.py` (2220l) → 6 modules (85-1470l)
- [x] `api/v2/cas.py` (1245l) → 6 modules (35-459l)
- [x] `api/v2/system.py` (1556l) → 9 modules (92-488l)

### Backend Services ✅
- [x] `services/backup_service.py` (2351l) → 11 modules (123-502l)
  - backup_service.py (337l)
  - export_core.py (483l)
  - export_extended.py (502l)
  - decrypt_mixin.py (147l)
  - restore_core.py (400l)
  - restore_rbac.py (123l)
  - restore_auth.py (129l)
  - restore_notifications.py (62l)
  - restore_policies.py (110l)
  - restore_extended.py (303l)

### Backend Services ⏳
- [ ] `services/trust_store.py` (1487l) → À faire
- [ ] `services/acme/acme_service.py` (1456l) → À faire
- [ ] `services/pdf_report_service.py` (1298l) → À faire
- [ ] `services/scep_service.py` (981l) → À faire
- [ ] `services/cert_service.py` (944l) → À faire
- [ ] `services/discovery_service.py` (928l) → À faire
- [ ] `services/opnsense_import.py` (884l) → À faire
- [ ] `services/database_admin_service.py` (817l) → À faire
- [ ] `services/acme/acme_proxy_service.py` (998l) → À faire
- [ ] `services/acme/acme_client_service.py` (930l) → À faire
- [ ] `services/ca_service.py` (788l) → Optimisation possible

### Backend API ⏳
- [ ] `api/v2/sso.py` (1843l)
- [ ] `api/v2/ssh_cas.py` (1607l)
- [ ] `api/v2/settings.py` (1314l)
- [ ] `api/v2/users.py` (934l)
- [ ] `api/v2/acme_client.py` (918l)
- [ ] `api/v2/tools.py` (853l)
- [ ] `api/v2/acme.py` (849l)
- [ ] `api/v2/account.py` (806l)

### Modèles ⏳
- [ ] `models/__init__.py` (1180l) → Split en modèles individuels

### Frontend ⏳
- [ ] `pages/SettingsPage.jsx` (4833l)
- [ ] `pages/ACMEPage.jsx` (3527l)
- [ ] `pages/DiscoveryPage.jsx` (1854l)
- [ ] `pages/CAsPage.jsx` (1693l)
- [ ] `pages/CertificatesPage.jsx` (1464l)

---

## 📅 Historique des commits

| Date | Commit | Description | Fichiers modifiés |
|------|--------|-------------|------------------|
| 2026-05-01 | aaae72f1 | docs(refactor): add comprehensive refactoring plan | REFACTORING_PLAN.md |
| 2026-05-01 | 317253e9 | refactor(backend): split certificates.py (2220l) into modular structure | api/v2/certificates/ |
| 2026-05-01 | f21e9ff8 | docs(refactor): update REFACTORING_PLAN.md with certificates.py progress | REFACTORING_PLAN.md |
| 2026-05-01 | e208d468 | docs(refactor): update plan with next steps | REFACTORING_PLAN.md |
| 2026-05-01 | 8f9f15f0 | refactor(backend): split cas.py (1245l) into modular structure | api/v2/cas/ |
| 2026-05-01 | b255a2dd | docs(refactor): update plan with cas.py completion | REFACTORING_PLAN.md |
| 2026-05-01 | 2d418f76 | fix(backend): use English docstrings for consistency | backend/**/*.py |
| 2026-05-01 | 678d7553 | refactor(backend): split system.py (1556l) into modular structure | api/v2/system/ |
| 2026-05-01 | 4d2404d2 | docs(refactor): update plan with system.py completion | REFACTORING_PLAN.md |
| 2026-05-01 | 516d8695 | refactor(services): split restore_mixin.py into modular restore mixins | services/backup/ |
| 2026-05-01 | f30c09f4 | fix(services): add missing model imports to backup mixins | services/backup/ |

---

## 🎯 Prochaines étapes

### Priorité 1: `services/ca_service.py` (788l) - Optimisation
**Objectif :** Réduire redondances, clarifier responsabilités
- [ ] Analyser les dépendances
- [ ] Extraire helpers communs (fichiers, audit)
- [ ] Split en 5-6 modules
- [ ] Supprimer code dupliqué
- [ ] Tester : `pytest backend/tests/test_cas.py -x -q`
- [ ] Commiter : `refactor(services): split ca_service.py into modular structure`

### Priorité 2: Services > 1400 lignes
- [ ] `services/trust_store.py` (1487l)
- [ ] `services/acme/acme_service.py` (1456l)
- [ ] `services/pdf_report_service.py` (1298l)

### Priorité 3: Services > 800 lignes
- [ ] `services/scep_service.py` (981l)
- [ ] `services/cert_service.py` (944l)
- [ ] `services/discovery_service.py` (928l)
- [ ] `services/opnsense_import.py` (884l)
- [ ] `services/database_admin_service.py` (817l)

---

## 💡 Notes et Bonnes Pratiques

### Pattern de split validé (backup_service)
```
services/backup/
├── __init__.py              # from .backup_service import BackupService
├── backup_service.py        # Classe principale (330l)
├── decrypt_mixin.py         # Méthodes de décryptage (147l)
├── export_core.py           # Export principaux (483l)
├── export_extended.py       # Export étendus (502l)
├── restore_core.py          # Restauration core (400l)
├── restore_rbac.py          # RBAC restore (123l)
├── restore_auth.py          # Auth restore (129l)
├── restore_notifications.py # Notifications restore (62l)
├── restore_policies.py      # Policies restore (110l)
└── restore_extended.py      # Extended restore (303l)
```

**Leçons apprises :**
1. ✅ Mixin pattern fonctionne bien pour conserver le `self` contexte
2. ✅ Chaque mixin importe ses propres dépendances
3. ✅ Wrapper file pour compatibilité descendante
4. ⚠️ Vérifier que tous les modèles sont importés dans chaque module
5. ⚠️ Gérer les cas legacy (ex: configuration comme liste vs dict)

### Instructions de déploiement et test (netsuit)
```bash
# Build frontend
cd /root/ucm-src/frontend && npm run build

# Déployer sur netsuit
sudo chown -R ucm:ucm /opt/ucm/  # IMPORTANT: Fix permissions
sudo rm -rf /opt/ucm/frontend/dist/*
sudo cp -r /root/ucm-src/frontend/dist/* /opt/ucm/frontend/dist/
sudo cp -r /root/ucm-src/backend/* /opt/ucm/backend/
sudo cp /root/ucm-src/VERSION /opt/ucm/VERSION
sudo systemctl restart ucm

# Vérifier
curl -sk https://netsuit.lan.pew.pet:8443/api/v2/health
```

### Checklist avant commit
- [ ] `pytest backend/tests/ -x -q` (tous les tests passent)
- [ ] `cd frontend && npm test` (tous les tests frontend passent)
- [ ] Vérifier les imports circulaires avec `python3 -c "from X import Y"`
- [ ] Vérifier la taille des fichiers : `wc -l fichier.py`
- [ ] Message de commit au format conventional (anglais, impératif)
- [ ] Mettre à jour REFACTORING_PLAN.md

---

## ⚠️ Problèmes rencontrés et solutions

### Problème 1: ModuleNotFoundError pour models.scep et models.audit
**Cause :** Ces classes sont définies dans `models/__init__.py`, pas dans des modules séparés.
**Solution :** Importer depuis `models` au lieu de `models.scep` ou `models.audit`.
**Fichiers concernés :** `services/backup/export_extended.py`
**Commit :** f30c09f4

### Problème 2: configuration comme liste au lieu de dict dans les backups
**Cause :** Certains anciens backups ont `configuration` comme une liste vide `[]`.
**Solution :** Vérifier le type avant d'appeler `.get()` : `if isinstance(configuration, list): config_data = {}`
**Fichiers concernés :** `services/backup/restore_core.py`
**Commit :** f30c09f4

### Problème 3: ImportError pour encrypt_private_key dans export_core.py
**Cause :** Les méthodes utilisent des modèles non importés au niveau du module.
**Solution :** Ajouter tous les imports de modèles au début de chaque fichier de mixin.
**Fichiers concernés :** `services/backup/export_core.py`, `services/backup/export_extended.py`
**Commit :** f30c09f4

---

*Dernière mise à jour : 2026-05-01*
