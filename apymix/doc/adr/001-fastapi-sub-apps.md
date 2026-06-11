# ADR-001 : FastAPI comme dispatcher et framework API

**Statut :** Accepté
**Date :** 2026-02-24

## Contexte

PAPI doit servir plusieurs APIs sous un même serveur. Chaque API doit avoir son propre schéma OpenAPI. Deux approches principales sont envisagées pour le dispatch des requêtes vers les sous-applications.

## Options envisagées

### Option A : Starlette (main) + FastAPI (sub-apps)

Utiliser Starlette pur pour l'application principale (dispatch uniquement) et FastAPI pour chaque sub-app métier.

- **Avantages :** App principale plus légère, séparation claire des responsabilités
- **Inconvénients :** Pas de validation ni de docs OpenAPI sur les routes principales (health, auth). Deux frameworks à maîtriser. Configuration des middleware différente.

### Option B : FastAPI partout (main + sub-apps)

Utiliser FastAPI comme application principale ET pour chaque sub-app.

- **Avantages :** API cohérente partout (validation, docs, dependency injection). Un seul framework. Les routes globales (auth, health) bénéficient aussi d'OpenAPI. FastAPI est construit SUR Starlette, donc pas de surcoût réel.
- **Inconvénients :** Légèrement plus de dépendances importées sur l'app principale (négligeable).

## Décision

**Option B : FastAPI partout.**

FastAPI est une surcouche de Starlette sans overhead significatif. Utiliser FastAPI comme app principale permet :
- D'avoir les routes d'auth et de health documentées dans OpenAPI
- D'utiliser le même système de dependency injection partout
- De simplifier la maintenance (un seul framework)

Le montage de sub-apps via `app.mount("/prefix", sub_app)` donne automatiquement un schéma OpenAPI séparé par sub-app.

## Conséquences

### Positives
- Cohérence technique sur tout le projet
- Documentation OpenAPI complète (y compris auth et health)
- Courbe d'apprentissage réduite

### Négatives
- Si le module `papi` est open-sourcé, il embarque FastAPI comme dépendance (mais c'est déjà le cas de facto)

### Risques
- Aucun risque identifié. FastAPI est le standard de facto pour les APIs Python modernes.
