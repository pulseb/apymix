# ADR-003 : Découverte automatique des sub-apps API

**Statut :** Accepté
**Date :** 2026-02-24

## Contexte

PAPI doit permettre d'ajouter de nouvelles APIs métier sans modifier le code du module technique (`papi/`). Le module doit rester **complètement agnostique** des APIs pour pouvoir être réutilisé (voire open-sourcé). 

Trois approches sont envisageables pour connecter les sub-apps à l'app principale.

## Options envisagées

### Option A : Enregistrement manuel

Chaque sub-app est importée et montée explicitement dans `papi/app.py`.

```python
from apis.wedding.app import app as wedding_app
main_app.mount("/wedding", wedding_app)
```

- **Avantages :** Explicite, simple à comprendre, contrôle total.
- **Inconvénients :** Le module `papi/` importe directement depuis `apis/` → couplage fort. Chaque nouvelle API nécessite une modification de `papi/app.py`.

### Option B : Fichier de configuration central

Un fichier `apis.yaml` à la racine liste les APIs à monter.

```yaml
apis:
  - module: apis.wedding.app
    prefix: /wedding
  - module: apis.finance.app
    prefix: /finance
```

- **Avantages :** Découplé (pas d'import dans `papi/`), facile à lire.
- **Inconvénients :** Fichier central à maintenir, pas de co-localisation (la config est séparée du code de l'API).

### Option C : Convention + manifest local (auto-discovery)

L'app factory scanne le dossier `apis/`. Chaque sous-dossier contenant un `app.py` avec une instance `app` (FastAPI) est automatiquement monté. Un `manifest.yaml` optionnel par API permet de surcharger les métadonnées.

- **Avantages :** Zéro configuration centrale, co-localisation (chaque API porte ses propres métadonnées), ajout d'une API = créer un dossier, convention simple et documentée.
- **Inconvénients :** "Magie" implicite (import dynamique), peut surprendre un nouveau contributeur. Nécessite une convention bien documentée.

## Décision

**Option C : Convention + manifest local (auto-discovery).**

C'est l'approche la plus alignée avec les objectifs du projet :

1. **Découplage total** : `papi/` ne connaît aucune API nommément
2. **Frictionless** : ajouter une API = créer un dossier avec `app.py`
3. **Flexible** : le `manifest.yaml` optionnel permet de personnaliser sans imposer

### Convention de découverte

Pour qu'un dossier dans `apis/` soit reconnu :

| Élément | Obligatoire | Description |
|---------|-------------|-------------|
| `app.py` avec `app = FastAPI(...)` | ✅ Oui | Point d'entrée de la sub-app |
| `manifest.yaml` | ❌ Non | Métadonnées : `name`, `prefix`, `description`, `version`, `enabled` |

### Valeurs par défaut (sans manifest)

| Champ | Valeur inférée |
|-------|----------------|
| `prefix` | `/<nom_du_dossier>` |
| `name` | Nom du dossier capitalisé |
| `enabled` | `true` |

### Conventions d'exclusion

- Les dossiers commençant par `_` sont ignorés (ex : `_archive/`)
- Les dossiers sans `app.py` sont ignorés silencieusement
- Un `manifest.yaml` avec `enabled: false` désactive l'API sans la supprimer

## Conséquences

### Positives
- Le module `papi/` est 100% agnostique des APIs → open-sourceable
- Ajouter une API ne nécessite aucune modification existante
- Le `manifest.yaml` offre de la flexibilité sans complexité
- La même convention est utilisée pour `fronts/` (cohérence)

### Négatives
- L'import dynamique (`importlib.import_module`) peut rendre le debugging moins intuitif
- Si un `app.py` a une erreur de syntaxe, le message d'erreur peut être moins clair

### Risques
- Risque de collision de préfixes si deux APIs ont le même nom de dossier → mitigé par la validation au démarrage
- Ordre de montage non déterministe → mitigé par le tri alphabétique des dossiers
