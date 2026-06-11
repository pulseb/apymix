# User Stories — PAPI

---

## EPIC-01 : Socle technique PAPI

### US-001 : App factory et montage de sub-apps

**En tant que** développeur,
**je souhaite** que l'application principale monte automatiquement les sub-apps enregistrées,
**afin de** n'avoir qu'un seul point d'entrée pour toutes les APIs.

**Critères d'acceptation :**
- [ ] L'app factory crée une instance FastAPI principale
- [ ] Les sub-apps sont montées sur des préfixes configurables (ex : `/wedding`)
- [ ] Le serveur démarre sans erreur avec `uvicorn papi.app:create_app --factory`

**Estimation :** S
**Epic :** EPIC-01

---

### US-002 : OpenAPI par sub-app

**En tant que** développeur,
**je souhaite** que chaque sub-app expose son propre schéma OpenAPI,
**afin de** documenter chaque API indépendamment.

**Critères d'acceptation :**
- [ ] Chaque sub-app a une page Swagger UI accessible (ex : `/wedding/docs`)
- [ ] Chaque sub-app a un endpoint `/openapi.json` propre
- [ ] Le schéma inclut le titre, la version et la description de l'API

**Estimation :** XS
**Epic :** EPIC-01

---

### US-003 : Configuration par environnement

**En tant que** développeur,
**je souhaite** charger la configuration depuis des variables d'environnement,
**afin de** adapter le comportement entre dev et prod sans modifier le code.

**Critères d'acceptation :**
- [ ] La configuration est gérée via Pydantic Settings (`BaseSettings`)
- [ ] Un fichier `.env` est supporté pour le développement local
- [ ] Les paramètres clés sont configurables : `DATABASE_URL`, `JWT_SECRET`, `ENV`, `DEBUG`

**Estimation :** S
**Epic :** EPIC-01

---

### US-004 : Abstraction base de données

**En tant que** développeur,
**je souhaite** utiliser SQLite en développement et PostgreSQL en production avec le même code,
**afin de** simplifier le développement local.

**Critères d'acceptation :**
- [ ] SQLAlchemy 2.0 async est configuré avec session factory
- [ ] Le moteur de BDD est déterminé par `DATABASE_URL`
- [ ] Une dépendance FastAPI `get_db` fournit une session par requête
- [ ] Les modèles SQLAlchemy fonctionnent sur les deux moteurs

**Estimation :** M
**Epic :** EPIC-01

---

### US-005 : Authentification JWT

**En tant qu'** administrateur,
**je souhaite** m'authentifier via JWT,
**afin de** accéder aux fonctionnalités d'administration de manière sécurisée.

**Critères d'acceptation :**
- [ ] Un endpoint `POST /auth/login` accepte email + mot de passe et retourne un JWT
- [ ] Un endpoint `POST /auth/refresh` permet de renouveler le token
- [ ] Les routes protégées vérifient le JWT via un middleware / dépendance
- [ ] Les mots de passe sont hashés (bcrypt ou argon2)
- [ ] Le JWT a une durée de vie configurable

**Estimation :** M
**Epic :** EPIC-01

---

### US-006 : Middleware partagés

**En tant que** développeur,
**je souhaite** que les middleware CORS, logging et gestion d'erreurs soient appliqués globalement,
**afin de** ne pas les reconfigurer pour chaque API.

**Critères d'acceptation :**
- [ ] CORS est configuré sur l'app principale (origines autorisées configurables)
- [ ] Les requêtes sont loguées avec méthode, path, status et durée
- [ ] Les exceptions non gérées retournent une réponse JSON standardisée
- [ ] Les erreurs de validation Pydantic retournent un format cohérent

**Estimation :** S
**Epic :** EPIC-01

---

## EPIC-04 : Déploiement & Infrastructure

### US-016 : Lancement local en une commande

**En tant que** développeur,
**je souhaite** lancer l'application avec une seule commande,
**afin de** développer rapidement.

**Critères d'acceptation :**
- [ ] `uvicorn papi.app:create_app --factory --reload` démarre l'app avec SQLite
- [ ] Un fichier `.env.example` documente les variables nécessaires
- [ ] Le `README.md` contient les instructions de quickstart

**Estimation :** S
**Epic :** EPIC-04

---

### US-017 : Déploiement Docker

**En tant que** développeur,
**je souhaite** déployer via Docker / docker-compose,
**afin de** simplifier la mise en production.

**Critères d'acceptation :**
- [ ] Un `Dockerfile` multi-stage produit une image optimisée
- [ ] Un `docker-compose.yml` lance l'app + PostgreSQL
- [ ] Les variables d'environnement sont documentées
- [ ] L'image pèse moins de 200 Mo

**Estimation :** M
**Epic :** EPIC-04

---

### US-018 : Migrations de base de données

**En tant que** développeur,
**je souhaite** que les migrations de schéma soient gérées automatiquement,
**afin de** faire évoluer le modèle de données sans intervention manuelle.

**Critères d'acceptation :**
- [ ] Alembic est configuré et fonctionne avec SQLite et PostgreSQL
- [ ] `alembic upgrade head` applique toutes les migrations
- [ ] `alembic revision --autogenerate` détecte les changements de modèle
- [ ] Les migrations sont versionnées dans le dépôt Git

**Estimation :** M
**Epic :** EPIC-04

---

## EPIC-05 : Opérations admin & qualité

### US-019 : Déclencher un seed API depuis le backend admin

**En tant qu'** administrateur,
**je souhaite** lancer manuellement le seed d'une application métier,
**afin de** réinitialiser rapidement les données de démo d'une API sans script manuel.

**Critères d'acceptation :**
- [ ] Un endpoint `GET /-/admin/seed` liste les APIs seedables
- [ ] Un endpoint `POST /-/admin/seed/{api_name}` déclenche le seed ciblé
- [ ] L'accès est réservé aux sessions admin authentifiées
- [ ] La réponse indique si des données ont effectivement été insérées (`seeded: true/false`)

**Estimation :** S
**Epic :** EPIC-05

---

### US-020 : Couverture pytest des routes système critiques

**En tant que** développeur,
**je souhaite** disposer de tests `pytest` pour les routes système sensibles,
**afin de** sécuriser les évolutions backend.

**Critères d'acceptation :**
- [ ] Les routes de seed admin sont testées (auth, 404, succès)
- [ ] Les tests s'exécutent localement via `uv run pytest`
- [ ] Les tests n'écrivent pas dans la base de développement par défaut

**Estimation :** S
**Epic :** EPIC-05

---

## EPIC-06 : Authentification fédérée (OIDC)

### US-021 : Connexion admin via Google OIDC

**En tant qu'** administrateur,
**je souhaite** me connecter avec mon compte Google,
**afin de** accéder au back-office sans gérer un mot de passe local supplémentaire.

**Critères d'acceptation :**
- [ ] Un endpoint de redirection OIDC est disponible (`/-/auth/oidc/google/login`)
- [ ] Un callback OIDC valide l'identité et crée/met à jour l'utilisateur local
- [ ] L'utilisateur connecté reçoit un JWT interne PAPI pour les routes protégées
- [ ] L'accès admin reste conditionné au rôle `admin` côté base PAPI

**Estimation :** M
**Epic :** EPIC-06

---

### US-022 : Ajouter GitHub comme provider OIDC secondaire

**En tant que** développeur,
**je souhaite** ajouter GitHub comme second provider OIDC,
**afin de** offrir une alternative de connexion sans modifier l'architecture auth.

**Critères d'acceptation :**
- [ ] Le provider GitHub est activable par configuration (feature flag/env)
- [ ] Le flux login/callback réutilise le même socle que Google
- [ ] Les claims utiles (email, sub) sont normalisés dans le modèle utilisateur interne

**Estimation :** S
**Epic :** EPIC-06

---

## EPIC-07 : Images profilées par application

### US-023 : Build Docker par profil applicatif

**En tant que** développeur,
**je souhaite** construire une image selon un profil (`all`, `eve`, `kif`),
**afin de** déployer uniquement les apps nécessaires selon l'environnement.

**Critères d'acceptation :**
- [ ] Une commande de build accepte un profil (script ou argument standardisé)
- [ ] Le profil `all` conserve le comportement actuel (toutes apps incluses)
- [ ] Le profil `eve` inclut uniquement `eve-api` et le front `eve`
- [ ] La documentation de build/deploy décrit clairement les profils disponibles

**Estimation :** M
**Epic :** EPIC-07

---

### US-024 : Service mono-front sur la racine `/`

**En tant qu'** invité,
**je souhaite** accéder à un front mono-app directement sur `/`,
**afin de** éviter les préfixes d'URL dans un déploiement dédié.

**Critères d'acceptation :**
- [ ] En profil mono-front, le front actif est monté sur `/`
- [ ] Les assets statiques et routes SPA/PWA fonctionnent sans préfixe
- [ ] Les autres fronts ne sont pas montés dans ce profil

**Estimation :** M
**Epic :** EPIC-07

---

### US-025 : Sécuriser le schéma HTTPS derrière reverse proxy

**En tant qu'** administrateur,
**je souhaite** que l'admin UI serve toutes ses ressources en HTTPS,
**afin de** éviter les alertes navigateur et le mixed content.

**Critères d'acceptation :**
- [ ] L'application interprète correctement `X-Forwarded-Proto` derrière le proxy de confiance
- [ ] Les URLs générées pour SQLAdmin utilisent `https://` en production
- [ ] Aucun asset admin n'est chargé en `http://` depuis le navigateur

**Estimation :** S
**Epic :** EPIC-07
