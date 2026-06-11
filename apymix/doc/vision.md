# Vision — PAPI (Pluri API)

## Pitch

**PAPI (Pluri API)** est un socle technique Python permettant d'héberger plusieurs micro-APIs sous une même infrastructure. Il mutualise les préoccupations transverses (authentification, base de données, configuration, déploiement) pour qu'un développeur solo puisse déployer de nouvelles APIs métier sans friction.

## Problème

Un développeur qui a besoin de plusieurs petites APIs (RSVP mariage, gestion perso, domotique…) doit à chaque fois :

- Configurer un nouveau projet
- Mettre en place l'authentification
- Configurer la base de données et les migrations
- Écrire un Dockerfile et un pipeline CI/CD
- Gérer l'hébergement

**C'est un frein majeur** : la partie technique prend plus de temps que la logique métier elle-même.

## Solution

PAPI fournit :

1. **Un module technique réutilisable** (`papi/`) — auth, BDD, config, middleware — potentiellement open-sourceable
2. **Un système de sub-apps** — chaque API métier est un dossier dans `apis/` avec sa propre doc OpenAPI
3. **Un déploiement unique** — un seul conteneur Docker sert toutes les APIs
4. **Une abstraction BDD** — SQLite en dev, PostgreSQL en prod, même code

## Personas

### 👨‍💻 Développeur (persona principal de PAPI)

- **Profil :** Développeur solo ou petite équipe
- **Besoin :** Déployer rapidement des micro-APIs sans overhead technique
- **Interaction :** Crée des sub-apps dans `apis/`, utilise le module `papi/`

### 🔧 Administrateur

- **Profil :** Le développeur dans son rôle d'administrateur de la plateforme
- **Besoin :** Gérer les utilisateurs, surveiller les APIs, contrôler les accès
- **Interaction :** Interface d'administration, gestion des JWT, monitoring

## Périmètre

### Dans le périmètre

- ✅ Module technique PAPI (app factory, auth JWT, abstraction BDD, config)
- ✅ Système de montage de sub-apps avec OpenAPI par API
- ✅ Auto-discovery des APIs (`apis/`) et des frontends (`fronts/`)
- ✅ Registre d'applications (`papi_apps`)
- ✅ Déploiement Docker
- ✅ Back-office SQLAdmin

### Hors périmètre

- ❌ Logique métier (chaque API dans `apis/` gère la sienne)
- ❌ Frontends (chaque app dans `fronts/` est autonome)
- ❌ Multi-tenancy
- ❌ CI/CD complet (sera fait post-MVP)
- ❌ Monitoring / observabilité avancée

## Valeurs directrices

1. **Simplicité** — Un développeur doit pouvoir ajouter une API en < 30 minutes
2. **Isolation** — Chaque API métier est indépendante, le module technique est réutilisable
3. **Pragmatisme** — Pas d'over-engineering, on construit ce dont on a besoin
4. **Sécurité** — Les données personnelles sont protégées dès le départ (auth, HTTPS, validation)
