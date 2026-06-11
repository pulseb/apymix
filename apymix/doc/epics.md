# Epics — PAPI

## EPIC-01 : Socle technique PAPI

**Objectif :** Créer le module technique réutilisable qui permet de monter et servir plusieurs sub-apps FastAPI avec authentification, base de données et configuration partagées.

**Personas concernés :** Développeur, Administrateur

**Critères de succès :**
- Un développeur peut ajouter une nouvelle API en créant un dossier dans `apis/` et en l'enregistrant dans l'app factory
- Chaque sub-app a son propre schéma OpenAPI accessible
- L'authentification JWT est fonctionnelle et partagée entre les APIs
- La base de données fonctionne en SQLite (dev) et PostgreSQL (prod) sans changement de code métier
- Les middleware (CORS, logging, errors) sont appliqués globalement

**User Stories rattachées :** US-001, US-002, US-003, US-004, US-005, US-006

---

## EPIC-04 : Déploiement & Infrastructure

**Objectif :** Mettre en place l'infrastructure de déploiement pour que PAPI soit accessible en production de manière sécurisée.

**Personas concernés :** Développeur, Administrateur

**Critères de succès :**
- L'application peut être lancée localement avec une seule commande
- L'application peut être déployée via Docker / docker-compose
- La configuration est gérée par variables d'environnement
- HTTPS est en place en production

**User Stories rattachées :** US-016, US-017, US-018

---

## EPIC-05 : Opérations admin & qualité

**Objectif :** Faciliter l'exploitation quotidienne du backend et garantir un socle de tests automatisés sur les fonctionnalités critiques.

**Personas concernés :** Développeur, Administrateur

**Critères de succès :**
- Un admin authentifié peut déclencher manuellement le seed d'une API depuis le backend
- Les endpoints critiques disposent de tests `pytest`
- Les tests peuvent être lancés localement via `uv run pytest`

**User Stories rattachées :** US-019, US-020

---

## EPIC-06 : Authentification fédérée (OIDC)

**Objectif :** Ajouter une authentification SSO standard OIDC pour simplifier l'accès administrateur sans gérer de mots de passe locaux supplémentaires.

**Personas concernés :** Administrateur, Développeur

**Critères de succès :**
- Un administrateur peut se connecter via Google OIDC
- L'application conserve un mode JWT interne après authentification OIDC
- Les comptes OIDC sont reliés à un utilisateur interne avec rôle (`admin`/`user`)
- La configuration se fait par variables d'environnement (`OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`)

**User Stories rattachées :** US-021, US-022

---

## EPIC-07 : Images profilées par application

**Objectif :** Produire des images Docker ciblées par application (ex: `eve:latest`) tout en conservant une image `all-in-one` pour les environnements de test.

**Personas concernés :** Développeur, Administrateur

**Critères de succès :**
- Un build peut cibler un profil (`all`, `eve`, `kif`)
- Le profil détermine les APIs/fronts inclus et activés
- Le mode mono-front peut servir l'application sur `/` (sans préfixe)
- Le processus de build reste KISS (une commande principale)

**User Stories rattachées :** US-023, US-024, US-025
