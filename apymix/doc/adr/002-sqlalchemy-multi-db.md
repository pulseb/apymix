# ADR-002 : SQLModel pour l'abstraction multi-BDD (modèles unifiés)

**Statut :** Accepté (révisé)
**Date :** 2026-02-24

## Contexte

PAPI doit fonctionner avec SQLite en développement (simplicité, pas de serveur à installer) et PostgreSQL en production (robustesse, performance, concurrence). Le code métier ne doit pas changer entre les deux environnements.

De plus, dans un contexte de développeur solo, la duplication entre modèles SQLAlchemy (ORM) et schémas Pydantic (validation/sérialisation) est un overhead significatif : chaque champ est déclaré deux fois, et les deux doivent rester synchronisés manuellement.

## Options envisagées

### Option A : SQLAlchemy 2.0 (async) + Pydantic séparés

ORM Python le plus mature, avec support async via `asyncio` et drivers spécifiques (`aiosqlite`, `asyncpg`). Les schémas Pydantic sont déclarés séparément.

- **Avantages :** Écosystème mature, documentation riche, Alembic pour les migrations, support multi-moteur natif, pattern `Mapped[]` moderne, communauté large, contrôle total.
- **Inconvénients :** Duplication modèle/schéma (chaque champ déclaré deux fois), plus de boilerplate, synchronisation manuelle entre ORM et schéma.

### Option B : Tortoise ORM

ORM async-first pour Python, inspiré de Django ORM.

- **Avantages :** API simple, async natif, moins de boilerplate.
- **Inconvénients :** Écosystème plus petit, moins de drivers supportés, migrations moins matures (Aerich), communauté plus petite, incertitude sur la pérennité.

### Option C : SQLModel

Bibliothèque créée par Sebastián Ramírez (tiangolo, créateur de FastAPI) combinant SQLAlchemy + Pydantic en un seul modèle.

- **Avantages :** Un seul modèle = ORM + schéma de validation/sérialisation. Intégration native avec FastAPI (même auteur). Construit SUR SQLAlchemy 2.0 (donc Alembic fonctionne). Moins de code à maintenir. Courbe d'apprentissage douce pour qui connaît Pydantic et FastAPI.
- **Inconvénients :** Encore en version 0.x. Certains patterns avancés de SQLAlchemy sont moins accessibles. Les relations many-to-many nécessitent un peu plus de configuration.

### Option D : DuckDB

Base de données analytique embarquée.

- **Avantages :** Performant pour l'analytique, pas de serveur.
- **Inconvénients :** Orienté OLAP, pas conçu pour le CRUD transactionnel, pas de support SQLAlchemy natif, pas de mode multi-connexion concurrent en écriture.

## Décision

**Option C : SQLModel.**

Pour un développeur solo avec des APIs CRUD simples, la réduction de boilerplate est déterminante :

```python
# AVANT (SQLAlchemy + Pydantic séparés) : ~30 lignes pour un modèle
class RSVPModel(Base):                    # ORM
    __tablename__ = "rsvps"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    fullname: Mapped[str] = mapped_column(String(200))
    # ... répéter chaque champ

class RSVPCreate(BaseModel):              # Pydantic (input)
    fullname: str
    # ... re-déclarer chaque champ

class RSVPRead(BaseModel):                # Pydantic (output)
    id: uuid.UUID
    fullname: str
    # ... encore une fois

# APRÈS (SQLModel) : ~15 lignes pour le même résultat
class RSVP(TimestampMixin, table=True):   # ORM (table=True)
    __tablename__ = "rsvps"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(max_length=255, unique=True)
    fullname: str = Field(max_length=200)
    attending: bool = False
    guests: list | None = Field(default=None, sa_column=Column(JSON))

class RSVPCreate(SQLModel):               # Input (validation Pydantic)
    email: EmailStr
    fullname: str = Field(min_length=3, max_length=200)
    attending: bool
    guests: list[GuestItem] = []

class RSVPRead(SQLModel):                 # Output
    id: uuid.UUID
    fullname: str
    guest_count: int                      # calculé : len(guests) + 1
```

SQLModel est construit SUR SQLAlchemy 2.0, donc :
- Alembic fonctionne normalement pour les migrations
- Les drivers `aiosqlite` et `asyncpg` sont supportés
- On peut descendre au niveau SQLAlchemy pour les cas avancés

DuckDB est écarté car orienté analytique (OLAP), pas transactionnel (OLTP).

## Conséquences

### Positives
- **DRY** : chaque champ n'est déclaré qu'une seule fois
- Migrations versionnées via Alembic (identique à SQLAlchemy pur)
- Validation Pydantic intégrée dans les modèles ORM
- Même auteur que FastAPI = intégration naturelle et cohérente
- Moins de code = moins de bugs, maintenance simplifiée

### Négatives
- Version 0.x (mais largement utilisée en production, auteur actif)
- Si le module `papi` est open-sourcé, la dépendance à SQLModel (plutôt que SQLAlchemy seul) peut être un frein pour certains utilisateurs avancés
- Il faut activer `PRAGMA foreign_keys = ON` pour SQLite

### Risques
- Si SQLModel stagne, on peut migrer vers SQLAlchemy pur (les modèles `table=True` SONT des modèles SQLAlchemy). Le risque de lock-in est faible.
- Si des fonctionnalités PostgreSQL spécifiques sont utilisées (JSONB, arrays), elles ne seront pas disponibles en SQLite. → Mitigation : s'en tenir aux types standards.
